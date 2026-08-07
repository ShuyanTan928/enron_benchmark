#!/usr/bin/env python3
"""Work vs Casual heatmap, one figure per clue-count n.

Rows = models, columns = (register, noise) with a work | casual divider. Each cell = mean FINAL over
BOTH mechanisms (com_n<n> + pal_n<n>) restricted to that register's topics at that noise.

Usage:  plot_heatmap_register.py 2   (or 3)
Writes results/eval_api_full/plots/E_work_casual_n<n>.png
"""
import csv
import statistics as st
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path("results/eval_api_full/plots")
OUT.mkdir(parents=True, exist_ok=True)
N = int(sys.argv[1]) if len(sys.argv) > 1 else 2
NOISES = [0, 200, 400]

WORK = {f"T{i:02d}" for i in list(range(1, 11)) + list(range(21, 26))}
CASUAL = {f"T{i:02d}" for i in list(range(11, 21)) + list(range(26, 31))}

MODELS = {
    "opus-4.8 (reason, 8t)": "results/eval_api_full/opus_r/raw.csv",
    "terra-pro":       "results/eval_api_full/terra_pro/raw.csv",
    "terra":           "results/eval_api_full/terra/raw.csv",
    "luna":            "results/eval_api_full/luna/raw.csv",
    "deepseek-v4-pro": "results/eval_api_full/deepseek_v4_pro/raw.csv",
    "gemma4-31b (local)": "results/eval_gemma_full/raw.csv",
}


def load(p):
    p = Path(p)
    return list(csv.DictReader(p.open())) if p.exists() else []


def cell(rows, register, noise):
    cfgs = {f"com_n{N}", f"pal_n{N}"}
    xs = [float(r["final"]) for r in rows
          if r["config"] in cfgs and int(r["noise"]) == noise
          and r["topic"] in register and r["final"] != ""]
    return st.mean(xs) if xs else float("nan")


data = {name: load(p) for name, p in MODELS.items()}
cols = [("work", n) for n in NOISES] + [("casual", n) for n in NOISES]
names = list(MODELS)
grid = [[cell(data[nm], WORK if reg == "work" else CASUAL, noise) for reg, noise in cols]
        for nm in names]

fig, ax = plt.subplots(figsize=(9, 3.8))
im = ax.imshow(grid, cmap="viridis", vmin=0, vmax=1, aspect="auto")
ax.set_xticks(range(len(cols)))
ax.set_xticklabels([f"{reg}\n{noise}" for reg, noise in cols], fontsize=8)
ax.set_yticks(range(len(names)))
ax.set_yticklabels(names, fontsize=9)
for i in range(len(names)):
    for j in range(len(cols)):
        v = grid[i][j]
        txt = "-" if v != v else f"{v:.2f}"
        ax.text(j, i, txt, ha="center", va="center",
                color="white" if (v != v or v < 0.55) else "black", fontsize=8)
ax.axvline(len(NOISES) - 0.5, color="black", lw=3)          # work | casual
fig.colorbar(im, ax=ax, label="FINAL score", shrink=0.8)
ax.set_title(f"Work vs Casual  (n={N},  commission + paltering combined)",
             fontweight="bold", fontsize=11)
fig.tight_layout()
fig.savefig(OUT / f"E_work_casual_n{N}.png", dpi=130)
plt.close(fig)
print("wrote:", OUT / f"E_work_casual_n{N}.png")
