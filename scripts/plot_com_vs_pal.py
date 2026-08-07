#!/usr/bin/env python3
"""Commission vs Paltering comparison — grouped bars, one pair per model.

For each model, commission = mean FINAL over (com_n2, com_n3); paltering = mean over (pal_n2, pal_n3),
at a chosen noise level. Shows the mechanism asymmetry: lying by commission is easier to catch than
paltering. Writes results/eval_api_full/plots/D_com_vs_pal.png
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
NOISE = int(sys.argv[1]) if len(sys.argv) > 1 else 400

# display name -> raw.csv  (only models that ran this noise level are drawn)
MODELS = {
    "opus-4.8\n(reason,8t)": "results/eval_api_full/opus_r/raw.csv",
    "terra-pro":             "results/eval_api_full/terra_pro/raw.csv",
    "terra":                 "results/eval_api_full/terra/raw.csv",
    "luna":                  "results/eval_api_full/luna/raw.csv",
    "deepseek\nv4-pro":      "results/eval_api_full/deepseek_v4_pro/raw.csv",
    "gemma4-31b\n(local)":   "results/eval_gemma_full/raw.csv",
}

C_COM, C_PAL = "#2c7fb8", "#e6842e"   # commission blue, paltering orange


def mech_final(rows, mech, noise):
    xs = [float(r["final"]) for r in rows
          if r["config"] in {f"{mech}_n2", f"{mech}_n3"}
          and int(r["noise"]) == noise and r["final"] != ""]
    return st.mean(xs) if xs else None


names, com, pal = [], [], []
for name, p in MODELS.items():
    p = Path(p)
    if not p.exists():
        continue
    rows = list(csv.DictReader(p.open()))
    c = mech_final(rows, "com", NOISE)
    q = mech_final(rows, "pal", NOISE)
    if c is None and q is None:
        continue                      # model didn't run this noise
    names.append(name)
    com.append(c or 0.0)
    pal.append(q or 0.0)

x = range(len(names))
w = 0.38
fig, ax = plt.subplots(figsize=(9, 4.2))
b1 = ax.bar([i - w / 2 for i in x], com, w, label="commission (a false statement)", color=C_COM)
b2 = ax.bar([i + w / 2 for i in x], pal, w, label="paltering (true-but-misleading)", color=C_PAL)
for bars in (b1, b2):
    for b in bars:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.01,
                f"{b.get_height():.2f}", ha="center", va="bottom", fontsize=8)
ax.set_xticks(list(x))
ax.set_xticklabels(names, fontsize=8)
ax.set_ylabel("mean FINAL score")
ax.set_ylim(0, 1)
ax.set_title(f"Commission vs Paltering  (noise {NOISE})  —  paltering is harder to detect",
             fontweight="bold", fontsize=11)
ax.legend(fontsize=9, loc="upper right")
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(OUT / "D_com_vs_pal.png", dpi=130)
plt.close(fig)
print("wrote:", OUT / "D_com_vs_pal.png", f"(noise={NOISE}, {len(names)} models)")
