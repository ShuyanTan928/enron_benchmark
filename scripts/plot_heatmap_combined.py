#!/usr/bin/env python3
"""Combined-mechanism heatmap leaderboard (com + pal averaged together).

Follows the format of results/eval_final/plots/C_heatmap.png:
  model (rows) x (n, noise) (cols) grid of mean FINAL, viridis, annotated, n2|n3 divider.
Each cell = mean FINAL over BOTH mechanisms (commission + paltering) at that (n, noise).

Writes results/eval_api_full/plots/C_heatmap.png
"""
import csv
import statistics as st
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path("results/eval_api_full/plots")
OUT.mkdir(parents=True, exist_ok=True)

NOISES = [0, 200, 400]
# display name -> raw.csv path  (order = top->bottom rows)
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


def combined_final(rows, n, noise):
    """mean FINAL over com_n<n> AND pal_n<n> at this noise (both mechanisms together)."""
    cfgs = {f"com_n{n}", f"pal_n{n}"}
    xs = [float(r["final"]) for r in rows
          if r["config"] in cfgs and int(r["noise"]) == noise and r["final"] != ""]
    return st.mean(xs) if xs else float("nan")


data = {name: load(p) for name, p in MODELS.items()}
cols = [(n, noise) for n in (2, 3) for noise in NOISES]
names = list(MODELS)
grid = [[combined_final(data[nm], n, noise) for (n, noise) in cols] for nm in names]

fig, ax = plt.subplots(figsize=(9, 3.8))
im = ax.imshow(grid, cmap="viridis", vmin=0, vmax=1, aspect="auto")
ax.set_xticks(range(len(cols)))
ax.set_xticklabels([f"n{n}\n{noise}" for n, noise in cols], fontsize=8)
ax.set_yticks(range(len(names)))
ax.set_yticklabels(names, fontsize=9)
for i in range(len(names)):
    for j in range(len(cols)):
        v = grid[i][j]
        txt = "-" if v != v else f"{v:.2f}"
        ax.text(j, i, txt, ha="center", va="center",
                color="white" if (v != v or v < 0.55) else "black", fontsize=8)
ax.axvline(len(NOISES) - 0.5, color="black", lw=3)          # divide n2 | n3
fig.colorbar(im, ax=ax, label="FINAL score", shrink=0.8)
ax.set_title("Leaderboard: mean FINAL by model x n x noise  (commission + paltering combined)",
             fontweight="bold", fontsize=10)
fig.tight_layout()
fig.savefig(OUT / "C_heatmap.png", dpi=130)
plt.close(fig)
print("wrote:", OUT / "C_heatmap.png")
