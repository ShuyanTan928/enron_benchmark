#!/usr/bin/env python3
"""Evaluate a model on the assembled benchmark (Step 5–7).

For each topic × noise level: assemble the haystack (clue emails embedded in real corpus noise),
the model reads the pile and answers detection / identification / grounding; an API judge checks the
identification against the answer key; a deterministic grounding check matches cited sentences to the
planted clue bodies; a 0–5 score is assigned. Sweeps noise as the difficulty dial. Writes a CSV.

  uv run python scripts/run_eval.py --engine vllm --preset gemma4-31b --tp 2 --noise 0,20,50,100
  uv run python scripts/run_eval.py --engine api  --preset or-gpt-5  --noise 0,50 --topics T01,T05  # smoke
"""
import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, "scripts")
sys.path.insert(0, ".")
from email_finalize import clue_to_thread, build_haystack
from src.models.engine_factory import build_engine

SOLVE = Path("prompts/eval_solve.md")
JUDGE = Path("prompts/eval_judge.md")


def render_pile(flat: list) -> str:
    blocks = []
    for m in flat:
        to = ", ".join(m.get("to_addrs", []) or [])
        cc = ", ".join(m.get("cc_addrs", []) or [])
        hdr = f"From: {m.get('from_addr', '')}\nTo: {to}" + (f"\nCc: {cc}" if cc else "")
        hdr += f"\nDate: {(m.get('date', '') or '')[:10]}\nSubject: {m.get('subject', '')}"
        blocks.append(hdr + "\n\n" + (m.get("body", "") or ""))
    return "\n\n----------------------------------------\n\n".join(blocks)


def solve(engine, pile: str) -> dict:
    out = engine.generate(SOLVE.read_text().replace("<<EMAILS>>", pile),
                          max_tokens=1200, temperature=0.0)[0]
    det = re.search(r"DETECTION:\s*(YES|NO)", out, re.I)
    ident = re.search(r"IDENTIFICATION:\s*(.+)", out)
    evid = re.findall(r"EVIDENCE:\s*(.+)", out)
    return {"detection": (det.group(1).upper() if det else "NO"),
            "identification": (ident.group(1).strip() if ident else "-"),
            "evidence": [e.strip() for e in evid if e.strip() and e.strip() != "-"]}


def judge(engine, ans: dict, det: str, ident: str) -> bool:
    p = (JUDGE.read_text().replace("<<ACTOR>>", ans.get("actor", ""))
         .replace("<<VICTIM>>", ans.get("victim", "")).replace("<<TRUE>>", ans.get("true_fact", ""))
         .replace("<<FALSE>>", ans.get("false_belief", "")).replace("<<DET>>", det)
         .replace("<<IDENT>>", ident))
    out = engine.generate(p, max_tokens=400, temperature=0.0)[0]
    m = re.search(r"\{.*\}", out, re.S)
    try:
        return bool(json.loads(m.group(0)).get("match")) if m else False
    except Exception:
        return False


def _toks(s):
    return set(re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).split())


def grounding(evidence: list, clue_bodies: list):
    """A citation is valid if its tokens overlap a planted clue body (>= 0.6 of the citation's tokens).
    precision = valid / cited; recall = distinct clue messages hit / total clue messages."""
    if not evidence:
        return 0.0, 0.0
    clue_tok = [_toks(b) for b in clue_bodies]
    valid, hit = 0, set()
    for e in evidence:
        et = _toks(e)
        best, bi = 0.0, -1
        for i, ct in enumerate(clue_tok):
            ov = len(et & ct) / max(1, len(et))
            if ov > best:
                best, bi = ov, i
        if best >= 0.6:
            valid += 1
            hit.add(bi)
    return valid / len(evidence), len(hit) / max(1, len(clue_bodies))


def score(det: str, match: bool, precision: float, recall: float) -> int:
    if det != "YES":
        return 0
    if not match:
        return 1
    if precision == 0:
        return 2
    if precision < 1:
        return 3
    if recall < 1:
        return 4
    return 5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["vllm", "api"], default="vllm")
    ap.add_argument("--preset", required=True, help="solver model")
    ap.add_argument("--tp", type=int, default=2)
    ap.add_argument("--gpu_mem", type=float, default=0.9)
    ap.add_argument("--judge-preset", default="or-gpt-5")
    ap.add_argument("--noise", default="0,20,50,100")
    ap.add_argument("--clues", default="benchmark_pool/email_generation_n2.jsonl")
    ap.add_argument("--corpus", default="data/enron_10/threads.jsonl")
    ap.add_argument("--topics", default="all")
    ap.add_argument("--seed", type=int, default=20260624)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    noises = [int(x) for x in args.noise.split(",") if x.strip()]
    objs = [json.loads(l) for l in Path(args.clues).read_text().splitlines() if l.strip()]
    objs = [o for o in objs if o.get("status", "KEPT") == "KEPT"]
    if args.topics != "all":
        keep = set(args.topics.split(","))
        objs = [o for o in objs if o["topic_id"] in keep]
    corpus = [json.loads(l) for l in Path(args.corpus).read_text().splitlines() if l.strip()]
    people = json.loads(Path("benchmark_pool/people.json").read_text())["people"]
    addr_map = {p["real_name"]: p["real_email"] for p in people}

    solver = build_engine(args.engine, args.preset, tp=args.tp, gpu_mem=args.gpu_mem)
    judge_eng = build_engine("api", args.judge_preset)
    out = Path(args.out or f"results/eval_new/{args.preset.replace('/', '_')}.csv")
    out.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    print(f"solver={args.preset}  judge={args.judge_preset}  noise={noises}  topics={len(objs)}")
    for noise in noises:
        for obj in objs:
            tid = obj["topic_id"]
            clue_threads = [clue_to_thread(c, tid, addr_map) for c in obj["clues"]]
            clue_bodies = [m["body"] for th in clue_threads for m in th["messages"]]
            _, _, flat = build_haystack(clue_threads, corpus, noise_target=noise, seed=args.seed)
            s = solve(solver, render_pile(flat))
            match = judge(judge_eng, obj.get("answer", {}), s["detection"], s["identification"]) \
                if s["detection"] == "YES" else False
            prec, rec = grounding(s["evidence"], clue_bodies)
            sc = score(s["detection"], match, prec, rec)
            rows.append({"model": args.preset, "topic": tid, "noise": noise, "detection": s["detection"],
                         "match": int(match), "precision": round(prec, 2), "recall": round(rec, 2),
                         "score": sc})
            print(f"  {tid} noise={noise:>3}: det={s['detection']:3} match={int(match)} "
                  f"P={prec:.2f} R={rec:.2f} -> score {sc}")

    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nWROTE {out}  ({len(rows)} rows)")
    for noise in noises:
        sc = [r["score"] for r in rows if r["noise"] == noise]
        print(f"  noise={noise:>3}: avg score {sum(sc)/len(sc):.2f}")


if __name__ == "__main__":
    main()
