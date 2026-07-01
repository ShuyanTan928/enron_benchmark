#!/usr/bin/env python3
"""Deferred judging pass: fill secret_match / final on a --no-judge raw.csv once the judge is back.

run_eval --no-judge saves each cell's `secret` text + deterministic recall/precision but leaves
secret_match / secret_score / final blank. This reads that raw.csv, judges every found=1 row's stated
secret against the answer key (same fixed Sonnet judge), and computes final = found*secret_match *
recall*precision. Rewrites raw.csv in place and regenerates summary.csv.

  uv run python scripts/judge_pass.py --dir results/eval_final/gemma4-31b
"""
import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, "scripts")
sys.path.insert(0, ".")
import run_eval as R
from src.models.engine_factory import build_engine

ap = argparse.ArgumentParser()
ap.add_argument("--dir", required=True)
ap.add_argument("--clues", default="benchmark_pool/emails_lying_n2.jsonl:n2,"
                                    "benchmark_pool/emails_lying_n3.jsonl:n3")
ap.add_argument("--judge-engine", default="api")
ap.add_argument("--judge-preset", default="anthropic/claude-sonnet-4.6")
ap.add_argument("--parallel", type=int, default=8)
ap.add_argument("--judge-max-tokens", type=int, default=300)
args = ap.parse_args()

# answer key per (config, topic)
answers = {}
for spec in args.clues.split(","):
    path, _, label = spec.partition(":")
    lab = label or Path(path).stem
    for line in Path(path).read_text().splitlines():
        if line.strip():
            o = json.loads(line)
            answers[(lab, o["topic_id"])] = o.get("answer", {})

raw = Path(args.dir) / "raw.csv"
rows = list(csv.DictReader(raw.open()))
todo = [i for i, r in enumerate(rows) if r["found"] == "1" and (r.get("secret") or "").strip()]
print(f"{raw}: {len(rows)} rows, judging {len(todo)} found+non-empty secrets with {args.judge_preset}")

eng = build_engine(args.judge_engine, args.judge_preset)
items = [(answers.get((rows[i]["config"], rows[i]["topic"]), {}), rows[i]["secret"]) for i in todo]
res = R.judge_batch(eng, items, args.judge_max_tokens, args.parallel)
match_by_idx = {i: res[k] for k, i in enumerate(todo)}

for i, r in enumerate(rows):
    found = int(r["found"])
    match = int(bool(match_by_idx.get(i, False)))
    ss = found * match
    es = float(r["evidence_score"]) if (r.get("evidence_score") or "") not in ("", "None") else 0.0
    r["secret_match"], r["secret_score"], r["final"] = match, ss, round(ss * es, 3)

fields = list(rows[0].keys())
with raw.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for r in rows:
        w.writerow(r)

# regenerate summary.csv (same shape run_eval writes)
def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0

configs = sorted({r["config"] for r in rows})
noises = sorted({int(r["noise"]) for r in rows})
sfields = ["config", "noise", "n_cells", "found_rate", "secret_score", "recall", "precision",
           "evidence_score", "final"]
with (Path(args.dir) / "summary.csv").open("w", newline="") as sf:
    sw = csv.DictWriter(sf, fieldnames=sfields)
    sw.writeheader()
    print("\n=== MEAN by config x noise ===")
    for label in configs:
        print(f"\n{label}:  noise | found | secret | evid | FINAL")
        for noise in noises:
            cell = [r for r in rows if r["config"] == label and int(r["noise"]) == noise]
            if not cell:
                continue
            srow = {"config": label, "noise": noise, "n_cells": len(cell),
                    "found_rate": round(mean([int(r["found"]) for r in cell]), 3),
                    "secret_score": round(mean([int(r["secret_score"]) for r in cell]), 3),
                    "recall": round(mean([float(r["recall"]) for r in cell]), 3),
                    "precision": round(mean([float(r["precision"]) for r in cell]), 3),
                    "evidence_score": round(mean([float(r["evidence_score"]) for r in cell]), 3),
                    "final": round(mean([float(r["final"]) for r in cell]), 3)}
            sw.writerow(srow)
            print(f"   {noise:>4}  | {srow['found_rate']:.2f}  | {srow['secret_score']:.2f}   | "
                  f"{srow['evidence_score']:.2f} | {srow['final']:.3f}")
print(f"\nfilled {raw} + summary.csv")
