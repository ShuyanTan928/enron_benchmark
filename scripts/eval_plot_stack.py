#!/usr/bin/env python3
"""100%-stacked bar of the 0-5 score COMPOSITION per noise level, for one model.

Each bar is a noise level; it is split into the fraction of topics that scored 0..5 (best score 5 at
the bottom, worst at the top), stacked to 100%, with the percentage labelled on each visible band. A
flat-green base that erodes as noise rises tells the difficulty story at a glance.

  uv run python scripts/eval_plot_stack.py results/eval_new/gemma4-31b.csv
  uv run python scripts/eval_plot_stack.py            # all results/eval_new/*.csv (one chart per model)
"""
import csv
import glob
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

LABELS = {5: "5 perfect", 4: "4 incomplete", 3: "3 noisy evid.",
          2: "2 no evid.", 1: "1 wrong id", 0: "0 no detect"}
CMAP = plt.cm.RdYlGn                                     # 0 red -> 5 green


def plot_model(rows, model, out):
    by = defaultdict(lambda: defaultdict(int))          # noise -> score -> count
    for r in rows:
        by[int(r["noise"])][int(r["score"])] += 1
    noises = sorted(by)
    x = range(len(noises))

    fig, ax = plt.subplots(figsize=(9, 5.5))
    bottom = [0.0] * len(noises)
    for s in [5, 4, 3, 2, 1, 0]:                         # best at the bottom
        fracs = []
        for n in noises:
            tot = sum(by[n].values()) or 1
            fracs.append(100.0 * by[n][s] / tot)
        ax.bar(x, fracs, bottom=bottom, width=0.7, color=CMAP(s / 5),
               edgecolor="white", linewidth=1.2, label=LABELS[s])
        for xi, (f, b) in enumerate(zip(fracs, bottom)):
            if f >= 4:                                   # label only visible bands
                ax.text(xi, b + f / 2, f"{f:.0f}%", ha="center", va="center",
                        color="black", fontsize=10, fontweight="bold")
        bottom = [b + f for b, f in zip(bottom, fracs)]

    ax.set_xticks(list(x))
    ax.set_xticklabels([f"noise {n}" for n in noises])
    ax.set_ylim(0, 100)
    ax.set_ylabel("share of topics (%)")
    ax.set_title(f"Score composition vs noise — {model}")
    ax.legend(ncol=6, loc="upper center", bbox_to_anchor=(0.5, -0.08), frameon=False, fontsize=9)
    fig.savefig(out, dpi=130, bbox_inches="tight")
    print("WROTE", out)


def main():
    files = sys.argv[1:] or sorted(glob.glob("results/eval_new/*.csv"))
    rows_by_model = defaultdict(list)
    for f in files:
        for r in csv.DictReader(open(f)):
            rows_by_model[r["model"]].append(r)
    for model, rows in rows_by_model.items():
        out = Path("results/eval_new") / f"score_stack_{model.replace('/', '_')}.png"
        plot_model(rows, model, out)


if __name__ == "__main__":
    main()
