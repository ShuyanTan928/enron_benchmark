#!/usr/bin/env python3
"""Plot avg 0–5 score vs noise for each evaluated model.

  uv run python scripts/eval_plot.py                       # all results/eval_new/*.csv
  uv run python scripts/eval_plot.py results/eval_new/gemma4-31b.csv ...
"""
import csv
import glob
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    files = sys.argv[1:] or sorted(glob.glob("results/eval_new/*.csv"))
    if not files:
        print("no CSVs in results/eval_new/")
        return
    plt.figure(figsize=(7.5, 5))
    for f in files:
        rows = list(csv.DictReader(open(f)))
        if not rows:
            continue
        model = rows[0]["model"]
        by = defaultdict(list)
        for r in rows:
            by[int(r["noise"])].append(int(r["score"]))
        xs = sorted(by)
        ys = [sum(by[x]) / len(by[x]) for x in xs]
        plt.plot(xs, ys, marker="o", label=f"{model} (n={len(rows)//max(1,len(xs))})")
    plt.xlabel("noise emails (difficulty dial)")
    plt.ylabel("avg score (0–5)")
    plt.title("Distributed-clue concealment detection vs noise")
    plt.ylim(-0.1, 5.1)
    plt.grid(alpha=0.3)
    plt.legend()
    out = Path("results/eval_new/score_vs_noise.png")
    plt.savefig(out, dpi=130, bbox_inches="tight")
    print("WROTE", out)


if __name__ == "__main__":
    main()
