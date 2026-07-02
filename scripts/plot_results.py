#!/usr/bin/env python3
"""Render the secret-recovery benchmark results as 3 complementary figures.

  A  leaderboard curves   : final vs noise, faceted n2|n3, one line/model + SEM band
  B  failure cascade      : per-model nested curves detection >= identification >= recovery (n3)
  C  heatmap leaderboard  : model x (config,noise) grid of mean final

Reads results/eval_final/<model>/raw.csv, writes results/eval_final/plots/{A,B,C}.png.
"""
import csv
import statistics as st
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path("results/eval_final")
OUT = ROOT / "plots"
OUT.mkdir(parents=True, exist_ok=True)
NOISES = [0, 100, 300, 600]
# short label -> (dir, color, marker)
MODELS = {
    "gemini-2.5-flash": ("google_gemini-2.5-flash", "#1f77b4", "o"),
    "haiku-4.5":        ("anthropic_claude-haiku-4.5", "#2ca02c", "s"),
    "deepseek-v4-pro":  ("deepseek_deepseek-v4-pro", "#ff7f0e", "^"),
    "gpt-5.4":          ("openai_gpt-5.4", "#d62728", "D"),
    "gemini-2.5-pro":   ("google_gemini-2.5-pro", "#9467bd", "P"),
    "gemma4-31b (local)": ("gemma4-31b", "#8c564b", "*"),
}


def load(dirname):
    p = ROOT / dirname / "raw.csv"
    return list(csv.DictReader(p.open())) if p.exists() else []


def cell(rows, cfg, noise):
    xs = [r for r in rows if r["config"] == cfg and int(r["noise"]) == noise]
    if not xs:
        return None
    g = lambda k: [float(r[k]) for r in xs]
    fin = g("final")
    return {
        "n": len(xs),
        "found": st.mean(g("found")),
        "ident": st.mean(g("secret_score")),        # found x secret_match
        "final": st.mean(fin),
        "sem": (st.pstdev(fin) / (len(fin) ** 0.5)) if len(fin) > 1 else 0.0,
    }


data = {name: load(d) for name, (d, _, _) in MODELS.items()}
cells = {name: {(c, n): cell(rows, c, n) for c in ("n2", "n3") for n in NOISES}
         for name, rows in data.items()}

# ---- A: leaderboard curves ---------------------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)
for ax, cfg in zip(axes, ("n2", "n3")):
    for name, (_, color, mk) in MODELS.items():
        pts = [(n, cells[name][(cfg, n)]) for n in NOISES if cells[name][(cfg, n)]]
        if not pts:
            continue
        xs = [n for n, c in pts]
        ys = [c["final"] for n, c in pts]
        es = [c["sem"] for n, c in pts]
        if len(pts) == 1:                            # flagship single point (@600)
            ax.errorbar(xs, ys, yerr=es, color=color, marker=mk, ms=10, capsize=4,
                        label=name, ls="none")
        else:
            ax.plot(xs, ys, color=color, marker=mk, label=name, lw=2)
            ax.fill_between(xs, [y - e for y, e in zip(ys, es)],
                            [y + e for y, e in zip(ys, es)], color=color, alpha=0.15)
    ax.set_title(f"{cfg}  ({'2 clues' if cfg == 'n2' else '3 clues, distributed'})")
    ax.set_xlabel("noise  (distractor emails in haystack)")
    ax.set_xticks(NOISES)
    ax.grid(alpha=0.3)
axes[0].set_ylabel("FINAL score  (secret recovery)")
axes[0].set_ylim(-0.02, 1.02)
axes[1].legend(fontsize=8, title="tester", loc="upper right")
fig.suptitle("A.  Secret recovery vs noise  (mean +/- SEM over 9 topics x 3 reps; Sonnet judge)",
             fontweight="bold")
fig.tight_layout()
fig.savefig(OUT / "A_curves.png", dpi=130)
plt.close(fig)

# ---- B: score breakdown — one figure PER NOISE, n2 | n3 side by side ---------------------------
# each model's bar sums to 1.0: recovered (final) | right secret, weak evidence | found but wrong
# secret | never detected.
SEGS = [("recovered (final)", "#2ca02c"),
        ("right secret, weak evidence", "#ffcc33"),
        ("found but WRONG secret", "#9e9e9e"),
        ("never detected", "#eeeeee")]


def breakdown_bar(ax, cfg, noise):
    names = [nm for nm in MODELS if cells[nm][(cfg, noise)]]
    x = range(len(names))
    rec = [cells[nm][(cfg, noise)]["final"] for nm in names]
    weak = [cells[nm][(cfg, noise)]["ident"] - cells[nm][(cfg, noise)]["final"] for nm in names]
    wrong = [cells[nm][(cfg, noise)]["found"] - cells[nm][(cfg, noise)]["ident"] for nm in names]
    none = [1 - cells[nm][(cfg, noise)]["found"] for nm in names]
    bottoms = [0.0] * len(names)
    for seg, vals in zip(SEGS, [rec, weak, wrong, none]):
        ax.bar(x, vals, bottom=bottoms, color=seg[1], edgecolor="white", label=seg[0])
        bottoms = [b + v for b, v in zip(bottoms, vals)]
    for i in range(len(names)):
        if rec[i] > 0.03:
            ax.text(i, rec[i] / 2, f"{rec[i]:.2f}", ha="center", va="center", fontsize=8, color="white")
    ax.set_title(f"{cfg}  ({'2 clues' if cfg == 'n2' else '3 clues'})", fontsize=11)
    ax.set_xticks(list(x))
    ax.set_xticklabels(names, rotation=40, ha="right", fontsize=8)
    ax.set_ylim(0, 1)


for noise in NOISES:
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 4.6), sharey=True)
    for ax, cfg in zip(axes, ("n2", "n3")):
        breakdown_bar(ax, cfg, noise)
    axes[0].set_ylabel("share of the full score (=1.0)")
    axes[0].legend(fontsize=8, loc="upper right", framealpha=0.95)
    fig.suptitle(f"B.  Score breakdown at noise = {noise}   (each bar = 1.0: got it vs. where it leaked)",
                 fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUT / f"B_noise{noise}.png", dpi=130)
    plt.close(fig)

# ---- C: heatmap leaderboard --------------------------------------------------------------------
cols = [(c, n) for c in ("n2", "n3") for n in NOISES]
names = list(MODELS)
grid = [[(cells[nm][col]["final"] if cells[nm][col] else float("nan")) for col in cols] for nm in names]
fig, ax = plt.subplots(figsize=(10, 3.6))
im = ax.imshow(grid, cmap="viridis", vmin=0, vmax=1, aspect="auto")
ax.set_xticks(range(len(cols)))
ax.set_xticklabels([f"{c}\n{n}" for c, n in cols], fontsize=8)
ax.set_yticks(range(len(names)))
ax.set_yticklabels(names, fontsize=9)
for i in range(len(names)):
    for j in range(len(cols)):
        v = grid[i][j]
        txt = "-" if v != v else f"{v:.2f}"
        ax.text(j, i, txt, ha="center", va="center",
                color="white" if (v != v or v < 0.55) else "black", fontsize=8)
ax.axvline(3.5, color="black", lw=3)                 # divide n2 | n3
fig.colorbar(im, ax=ax, label="FINAL score", shrink=0.8)
ax.set_title("C.  Leaderboard: mean FINAL by model x config x noise", fontweight="bold")
fig.tight_layout()
fig.savefig(OUT / "C_heatmap.png", dpi=130)
plt.close(fig)

print("wrote:", ", ".join(str(p.name) for p in sorted(OUT.glob("*.png"))))
