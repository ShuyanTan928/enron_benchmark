#!/usr/bin/env python3
"""Evaluate a tester model on the assembled benchmark with the SECRET-RECOVERY rubric.

For each clue-set (n=2, n=3) × topic × noise level × repeat: assemble the haystack (clue emails
embedded in real corpus noise, ids borrowed from the excised event cluster), the tester reads the
pile and fills ONE form:

    {"found": bool, "secret": "...", "evidence_email_ids": [...]}

Scoring (multiplicative gate — the secret gates everything):
    secret_score   = found ∈ {0,1}  ×  secret_match ∈ {0,1}      (an API/LLM judge decides the match)
    evidence_score = recall × precision ∈ [0,1]
        recall    = |cited ∩ true clues| / |true clues|
        precision = |cited that are clue emails| / |cited|
    final          = secret_score × evidence_score

`found`+judge kills blind guessing ("there is a secret" alone scores 0); evidence_score reads the
grounding quality. Sweeps noise as the difficulty dial, repeats each cell to average out sampling
variance. Writes a per-cell CSV and a per-(config,noise) summary CSV.

  uv run python scripts/run_eval.py --engine vllm --preset gemma4-31b --tp 2 \
      --noise 0,10,20,30,40,50,100 --reps 5
  uv run python scripts/run_eval.py --engine vllm --preset gemma4-31b --topics T02,T03 \
      --noise 0,20 --reps 1 --out results/smoke   # smoke
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, "scripts")
sys.path.insert(0, ".")
from email_finalize import clue_to_thread, build_haystack
from src.grounding.retrieval import BM25, tokenize
from src.models.engine_factory import build_engine

SOLVE = Path("prompts/eval_solve.md")
JUDGE = Path("prompts/eval_judge.md")
JAVAMAIL = re.compile(r"\d+\.\d+\.javamail\.evans@thyme", re.I)


# --- rendering / fitting ------------------------------------------------------------------------
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
    """Drop NOISE messages (never clue messages) from the pile until it fits the tester's context,
    preserving order. Clue messages are always kept so the secret stays recoverable — only the
    haystack is thinned at extreme noise on a small-context model. Returns (kept, truncated)."""
    if len(render_pile(flat)) <= budget_chars:
        return flat, False
    kept, size = [], 0
    for m in flat:
        block = len(render_pile([m])) + 44                # +separator
        if m.get("_source") == "clue" or size + block <= budget_chars:
            kept.append(m)
            size += block
    return kept, True


# --- tester (solve) + judge ---------------------------------------------------------------------
def _first_json(out: str):
    """Best-effort extract the first balanced {...} object and json.loads it."""
    i = out.find("{")
    while i != -1:
        depth, instr, esc = 0, False, False
        for j in range(i, len(out)):
            c = out[j]
            if instr:
                esc = (c == "\\" and not esc)
                if c == '"' and not esc:
                    instr = False
            elif c == '"':
                instr = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(out[i:j + 1])
                    except Exception:
                        break
        i = out.find("{", i + 1)
    return None


def parse_solve(out: str) -> dict:
    obj = _first_json(out) or {}
    found = bool(obj.get("found")) if "found" in obj else bool(re.search(r'"?found"?\s*:\s*true', out, re.I))
    secret = (obj.get("secret") or "").strip() if isinstance(obj.get("secret"), str) else ""
    ev = obj.get("evidence_email_ids")
    ids = []
    if isinstance(ev, list):                              # trust the model's explicit citation list
        for e in ev:
            ids += JAVAMAIL.findall(str(e))
    elif obj.get("secret") is None and not obj:           # JSON failed entirely -> scan whole output
        ids = JAVAMAIL.findall(out)
    return {"found": found, "secret": secret, "evidence_ids": list(dict.fromkeys(ids)), "raw": out[:4000]}


def _gen(engine, prompts, *, max_tokens, temperature, parallel):
    """vLLM (parallel<=1): one batched generate (continuous batching). API (parallel>1): fire the
    single-prompt calls over a thread pool, order preserved — vastly faster than APIEngine's
    sequential list handling."""
    if parallel <= 1:
        return engine.generate(prompts, max_tokens=max_tokens, temperature=temperature)
    from concurrent.futures import ThreadPoolExecutor

    def _one(p):
        try:
            return engine.generate([p], max_tokens=max_tokens, temperature=temperature)[0]
        except Exception as e:                    # one bad API response must not kill the whole sweep
            print(f"  [warn] API call failed ({str(e)[:100]}) -> scored empty", flush=True)
            return ""
    with ThreadPoolExecutor(max_workers=parallel) as ex:
        return list(ex.map(_one, prompts))


def solve_batch(engine, piles: list, temperature: float, max_tokens: int, parallel: int) -> list:
    prompts = [SOLVE.read_text().replace("<<EMAILS>>", p) for p in piles]
    outs = _gen(engine, prompts, max_tokens=max_tokens, temperature=temperature, parallel=parallel)
    return [parse_solve(o) for o in outs]


def judge_batch(engine, items: list, max_tokens: int, parallel: int) -> list:
    """items: list of (answer_dict, secret_str). Returns list[bool]."""
    if not items:
        return []
    prompts = []
    for ans, secret in items:
        prompts.append(JUDGE.read_text()
                       .replace("<<CONCEALMENT>>", ans.get("concealment", ""))
                       .replace("<<ACTOR>>", ans.get("actor", ""))
                       .replace("<<VICTIM>>", ans.get("victim", ""))
                       .replace("<<TRUE>>", ans.get("true_fact", ""))
                       .replace("<<FALSE>>", ans.get("false_belief", ""))
                       .replace("<<SECRET>>", secret or "(blank)"))
    outs = _gen(engine, prompts, max_tokens=max_tokens, temperature=0.0, parallel=parallel)
    res = []
    for o in outs:
        obj = _first_json(o) or {}
        res.append(bool(obj.get("match")))
    return res


# --- grounding / scoring ------------------------------------------------------------------------
def grounding(evidence_ids: list, clue_id_to_clue: dict, n_clues: int) -> tuple[float, float]:
    """Exact, clue-level grounding over Message-IDs. A cited id is VALID iff it belongs to a clue
    email; a clue (thread) is RECALLED iff ANY of its emails was cited (a 2-email chain is one unit).
    precision = valid cites / total cites ; recall = distinct clue threads hit / total clue threads."""
    if not evidence_ids:
        return 0.0, 0.0
    valid, hit = 0, set()
    for cid in evidence_ids:
        if cid in clue_id_to_clue:
            valid += 1
            hit.add(clue_id_to_clue[cid])
    return valid / len(evidence_ids), len(hit) / max(1, n_clues)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["vllm", "api"], default="vllm")
    ap.add_argument("--preset", required=True, help="tester model (also the judge unless --judge-preset)")
    ap.add_argument("--tp", type=int, default=2)
    ap.add_argument("--gpu_mem", type=float, default=0.9)
    ap.add_argument("--model-len", type=int, default=0,
                    help="override vLLM max_model_len (0=preset); raise for long-context local models")
    ap.add_argument("--judge-engine", default="api")
    ap.add_argument("--judge-preset", default="anthropic/claude-sonnet-4.6",
                    help="FIXED judge across every eval (consistency); pass '' to self-judge")
    ap.add_argument("--no-judge", action="store_true",
                    help="solve only: save `secret` text + deterministic recall/precision, leave "
                         "secret_match/final blank for a later judge_pass (use when the judge is down)")
    ap.add_argument("--noise", default="0,10,20,30,40,50,100")
    ap.add_argument("--reps", type=int, default=5, help="repeats per cell; averaged in the summary")
    ap.add_argument("--solve-temp", type=float, default=0.7, help="tester temperature (>0 for rep variance)")
    ap.add_argument("--solve-max-tokens", type=int, default=1500, help="raise for reasoning testers")
    ap.add_argument("--judge-max-tokens", type=int, default=300)
    ap.add_argument("--parallel", type=int, default=1, help="concurrent API calls (keep 1 for vLLM)")
    ap.add_argument("--max-ctx", type=int, default=32768,
                    help="pile char budget = f(max_ctx); set ~1000000 for big-context API models so "
                         "noise 200/500 is NOT trimmed")
    ap.add_argument("--clues", default="benchmark_pool/emails_lying_n2.jsonl:n2,"
                                       "benchmark_pool/emails_lying_n3.jsonl:n3",
                    help="comma list of file[:label] clue sets to sweep")
    ap.add_argument("--corpus", default="data/enron_10/threads.jsonl")
    ap.add_argument("--topics", default="all")
    ap.add_argument("--seed", type=int, default=20260624)
    ap.add_argument("--out", default="results/eval_rubric")
    args = ap.parse_args()

    noises = [int(x) for x in args.noise.split(",") if x.strip()]
    configs = []                                          # [(label, [objs])]
    keep = set(args.topics.split(",")) if args.topics != "all" else None
    for spec in args.clues.split(","):
        path, _, label = spec.partition(":")
        objs = [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]
        objs = [o for o in objs if o.get("status", "KEPT") == "KEPT"]
        if keep:
            objs = [o for o in objs if o["topic_id"] in keep]
        configs.append((label or Path(path).stem, objs))

    corpus = [json.loads(l) for l in Path(args.corpus).read_text().splitlines() if l.strip()]
    people = json.loads(Path("benchmark_pool/people.json").read_text())["people"]
    addr_map = {p["real_name"]: p["real_email"] for p in people}
    bm = BM25([(t.get("subject", "") or "") + " " + " ".join(m.get("body", "") or "" for m in t["messages"])
               for t in corpus])

    engine = build_engine(args.engine, args.preset, tp=args.tp, gpu_mem=args.gpu_mem,
                          max_model_len=(args.model_len or None))
    judge_eng = engine if not args.judge_preset else \
        build_engine(args.judge_engine or "api", args.judge_preset)
    solve_temp = args.solve_temp
    if "gpt-5" in args.preset.lower():             # GPT-5 rejects temperature != 1
        solve_temp = 1.0
        print(f"  [note] {args.preset}: forcing solve temperature=1.0")

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    raw_path, sum_path = outdir / "raw.csv", outdir / "summary.csv"
    budget_chars = max(4000, int((args.max_ctx - 1500 - 800) * 3.0))

    fields = ["config", "model", "topic", "n_clues", "noise", "rep", "found", "secret_match",
              "n_cited", "recall", "precision", "secret_score", "evidence_score", "final", "trunc",
              "secret"]
    rows = []
    jname = "OFF (deferred)" if args.no_judge else ("self" if judge_eng is engine else args.judge_preset)
    print(f"tester={args.preset}  judge={jname}  "
          f"configs={[c[0] for c in configs]}  noise={noises}  reps={args.reps}")
    f = raw_path.open("w", newline="")
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    try:
        for label, objs in configs:
            for rep in range(args.reps):
                seed = args.seed + rep
                for noise in noises:
                    piles, metas = [], []
                    for obj in objs:
                        tid = obj["topic_id"]
                        cts = [clue_to_thread(c, tid, addr_map) for c in obj["clues"]]
                        _, _, flat, _ = build_haystack(cts, corpus, obj.get("_anchor"), bm,
                                                       noise_target=noise, seed=seed)
                        c2c = {m["message_id"]: i for i, th in enumerate(cts) for m in th["messages"]}
                        flat, trunc = fit_pile(flat, budget_chars)
                        piles.append(render_pile(flat))
                        metas.append((obj, c2c, len(cts), trunc))
                    sols = solve_batch(engine, piles, solve_temp, args.solve_max_tokens, args.parallel)
                    if args.no_judge:
                        match_of = {}
                    else:
                        jidx = [i for i, s in enumerate(sols) if s["found"]]
                        jres = judge_batch(judge_eng, [(metas[i][0].get("answer", {}), sols[i]["secret"])
                                                       for i in jidx], args.judge_max_tokens, args.parallel)
                        match_of = {i: jres[k] for k, i in enumerate(jidx)}
                    for i, s in enumerate(sols):
                        obj, c2c, nclue, trunc = metas[i]
                        prec, rec = grounding(s["evidence_ids"], c2c, nclue)
                        es = rec * prec
                        row = {"config": label, "model": args.preset, "topic": obj["topic_id"],
                               "n_clues": nclue, "noise": noise, "rep": rep, "found": int(s["found"]),
                               "n_cited": len(s["evidence_ids"]), "recall": round(rec, 3),
                               "precision": round(prec, 3), "evidence_score": round(es, 3),
                               "trunc": int(trunc), "secret": s["secret"]}
                        if args.no_judge:                       # judging deferred -> leave blank
                            row.update(secret_match="", secret_score="", final="")
                        else:
                            match = bool(match_of.get(i, False))
                            ss = int(s["found"]) * int(match)
                            row.update(secret_match=int(match), secret_score=ss,
                                       final=round(ss * es, 3))
                        rows.append(row)
                        w.writerow(row)
                        f.flush()
                    tail = (f"found={sum(s['found'] for s in sols)}/{len(sols)} solve-only (judge deferred)"
                            if args.no_judge else
                            f"found={sum(s['found'] for s in sols)}/{len(sols)}  sum_final="
                            f"{sum(r['final'] for r in rows if r['config']==label and r['noise']==noise and r['rep']==rep):.2f}")
                    print(f"  [{label}] rep{rep} noise={noise:>3}: {tail}")
    finally:
        f.close()

    if args.no_judge:
        print(f"\nWROTE {raw_path}  ({len(rows)} rows, judge deferred)\n"
              f"run:  uv run python scripts/judge_pass.py --dir {outdir}   # when the judge is back up")
        return

    # --- aggregate: mean per (config, noise) over topics × reps ---------------------------------
    def mean(xs):
        return sum(xs) / len(xs) if xs else 0.0

    sfields = ["config", "noise", "n_cells", "found_rate", "secret_score", "recall", "precision",
               "evidence_score", "final"]
    with sum_path.open("w", newline="") as sf:
        sw = csv.DictWriter(sf, fieldnames=sfields)
        sw.writeheader()
        print(f"\nWROTE {raw_path}  ({len(rows)} rows)\n\n=== MEAN final by config × noise ===")
        for label, _ in configs:
            print(f"\n{label}:  noise |  found | secret | evid  | FINAL")
            for noise in noises:
                cell = [r for r in rows if r["config"] == label and r["noise"] == noise]
                srow = {"config": label, "noise": noise, "n_cells": len(cell),
                        "found_rate": round(mean([r["found"] for r in cell]), 3),
                        "secret_score": round(mean([r["secret_score"] for r in cell]), 3),
                        "recall": round(mean([r["recall"] for r in cell]), 3),
                        "precision": round(mean([r["precision"] for r in cell]), 3),
                        "evidence_score": round(mean([r["evidence_score"] for r in cell]), 3),
                        "final": round(mean([r["final"] for r in cell]), 3)}
                sw.writerow(srow)
                print(f"        {noise:>4}  |  {srow['found_rate']:.2f}  |  {srow['secret_score']:.2f}  |  "
                      f"{srow['evidence_score']:.2f}  |  {srow['final']:.3f}")
    print(f"\nWROTE {sum_path}")


if __name__ == "__main__":
    main()
