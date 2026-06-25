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
        hdr = f"Message-ID: <{m.get('message_id', '')}>\n"
        hdr += f"From: {m.get('from_addr', '')}\nTo: {to}" + (f"\nCc: {cc}" if cc else "")
        hdr += f"\nDate: {(m.get('date', '') or '')[:10]}\nSubject: {m.get('subject', '')}"
        blocks.append(hdr + "\n\n" + (m.get("body", "") or ""))
    return "\n\n----------------------------------------\n\n".join(blocks)


def fit_pile(flat: list, budget_chars: int) -> tuple[list, bool]:
    """Drop NOISE messages (never clue messages) from the date-ordered pile until it fits the model's
    context, preserving order. Clue messages are always kept so the secret stays recoverable — only
    the haystack is thinned at extreme noise on a small-context model. Returns (kept, truncated)."""
    if len(render_pile(flat)) <= budget_chars:
        return flat, False
    kept, size = [], 0
    for m in flat:
        block = len(render_pile([m])) + 44                # +separator
        if m.get("_source") == "clue" or size + block <= budget_chars:
            kept.append(m)
            size += block
    return kept, True


def solve(engine, pile: str) -> dict:
    out = engine.generate(SOLVE.read_text().replace("<<EMAILS>>", pile),
                          max_tokens=1200, temperature=0.0)[0]
    det = re.search(r"DETECTION:\s*(YES|NO)", out, re.I)
    ident = re.search(r"IDENTIFICATION:\s*(.+)", out)
    # the solver cites evidence as Message-IDs copied from the emails' headers
    ids = re.findall(r"\d+\.\d+\.javamail\.evans@thyme", out, re.I)
    return {"detection": (det.group(1).upper() if det else "NO"),
            "identification": (ident.group(1).strip() if ident else "-"),
            "evidence_ids": list(dict.fromkeys(ids))}


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


def grounding(evidence_ids: list, clue_id_to_clue: dict, n_clues: int):
    """Exact, clue-level grounding over Message-IDs. A cited id is VALID iff it belongs to a clue
    email; a clue (thread) is RECALLED iff ANY of its emails was cited — a 2-email chain is one unit.
    precision = valid cites / total cites ; recall = distinct clue threads hit / total clue threads."""
    if not evidence_ids:
        return 0.0, 0.0
    valid, hit = 0, set()
    for cid in evidence_ids:
        if cid in clue_id_to_clue:
            valid += 1
            hit.add(clue_id_to_clue[cid])
    return valid / len(evidence_ids), len(hit) / max(1, n_clues)


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
    ap.add_argument("--max-ctx", type=int, default=32768,
                    help="solver context window; the haystack is trimmed (noise only) to fit it")
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

    # haystack char budget so the prompt fits the solver context (reserve room for the solve template
    # + max_tokens output); ~3.0 chars/token is a conservative lower bound for English.
    budget_chars = max(4000, int((args.max_ctx - 1200 - 600) * 3.0))

    rows = []
    fields = ["model", "topic", "noise", "detection", "match", "precision", "recall", "trunc", "score"]
    print(f"solver={args.preset}  judge={args.judge_preset}  noise={noises}  topics={len(objs)}  "
          f"max_ctx={args.max_ctx}")
    # write incrementally so a crash (e.g. context overflow on one topic) keeps the rows already scored
    f = out.open("w", newline="")
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    try:
        for noise in noises:
            for obj in objs:
                tid = obj["topic_id"]
                clue_threads = [clue_to_thread(c, tid, addr_map) for c in obj["clues"]]
                _, _, flat = build_haystack(clue_threads, corpus, noise_target=noise, seed=args.seed)
                # after id-borrowing, map each clue email's real Message-ID -> its clue (thread) index
                clue_id_to_clue = {m["message_id"]: i for i, th in enumerate(clue_threads)
                                   for m in th["messages"]}
                flat, trunc = fit_pile(flat, budget_chars)
                s = solve(solver, render_pile(flat))
                match = judge(judge_eng, obj.get("answer", {}), s["detection"], s["identification"]) \
                    if s["detection"] == "YES" else False
                prec, rec = grounding(s["evidence_ids"], clue_id_to_clue, len(clue_threads))
                sc = score(s["detection"], match, prec, rec)
                row = {"model": args.preset, "topic": tid, "noise": noise, "detection": s["detection"],
                       "match": int(match), "precision": round(prec, 2), "recall": round(rec, 2),
                       "trunc": int(trunc), "score": sc}
                rows.append(row)
                w.writerow(row)
                f.flush()
                print(f"  {tid} noise={noise:>3}: det={s['detection']:3} match={int(match)} "
                      f"P={prec:.2f} R={rec:.2f}{' [trunc]' if trunc else '       '} -> score {sc}")
    finally:
        f.close()
    print(f"\nWROTE {out}  ({len(rows)} rows)")
    for noise in noises:
        sc = [r["score"] for r in rows if r["noise"] == noise]
        if sc:
            print(f"  noise={noise:>3}: avg score {sum(sc)/len(sc):.2f}")


if __name__ == "__main__":
    main()
