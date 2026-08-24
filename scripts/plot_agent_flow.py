"""Render the find-secrets agent tool-flow diagram to docs/agent_flow.png (no external SVG tooling)."""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.lines import Line2D

INK = "#1b2431"; MUT = "#5c6773"; ACC = "#2563eb"; AUTO = "#0d9488"
AUTO_T = "#e7f4f2"; PANEL = "#ffffff"

fig, ax = plt.subplots(figsize=(12.2, 6.2), dpi=170)
ax.set_xlim(0, 124); ax.set_ylim(0, 62); ax.axis("off")
fig.patch.set_facecolor(PANEL); ax.set_facecolor(PANEL)


def box(x, y, w, h, label, sub=None, edge=ACC, lc=INK, fs=14):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.6,rounding_size=2.0",
                                fc=PANEL, ec=edge, lw=1.8, mutation_aspect=1))
    ax.text(x + w / 2, y + h / 2 + (2.0 if sub else 0), label, ha="center", va="center",
            fontsize=fs, fontweight="bold", color=lc, family="DejaVu Sans")
    if sub:
        ax.text(x + w / 2, y + h / 2 - 2.9, sub, ha="center", va="center", fontsize=8.4,
                color=MUT, family="DejaVu Sans")


def arrow(x1, y1, x2, y2, color=MUT, rad=0.0, lw=1.7):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=14,
                                 color=color, lw=lw, connectionstyle=f"arc3,rad={rad}"))


# ---- tool boxes: LIST / SEGMENT (left) -> SEARCH <-> READ -> ANSWER --------------------------------
box(4, 44, 22, 10, "LIST", "orient")
box(4, 29, 22, 10, "SEGMENT", "scan coverage")
box(33, 37, 26, 10, "SEARCH", "BM25 - rerank 40 to 8")
box(66, 37, 18, 10, "READ", "full thread")
box(98, 37, 22, 10, "ANSWER", "up to N ranked + evidence")

arrow(1, 42, 4, 42)                                  # enter
arrow(26, 49, 33, 45)                                # LIST -> SEARCH
arrow(26, 34, 33, 40)                                # SEGMENT -> SEARCH
arrow(59, 42, 66, 42)                                # SEARCH -> READ
arrow(84, 42, 98, 42)                                # READ -> ANSWER (through the floor gate)
arrow(120, 42, 123, 42)                              # exit

# investigate loop READ -> SEARCH
arrow(70, 47, 48, 47, color=MUT, rad=0.42)
ax.text(59, 51.5, "investigate loop", ha="center", fontsize=9, color=MUT, style="italic")

# floor gate label
ax.text(91, 46.4, "floor gate", ha="center", fontsize=8.6, color=ACC)
ax.text(91, 37.8, "at least n distinct\nsearch / read probes", ha="center", va="center",
        fontsize=7.8, color=MUT)

# ---- auto box under READ --------------------------------------------------------------------------
ax.add_patch(FancyBboxPatch((46, 5), 58, 17, boxstyle="round,pad=0.6,rounding_size=2.0",
                            fc=AUTO_T, ec=AUTO, lw=1.5, ls=(0, (5, 3)), mutation_aspect=1))
ax.text(75, 18.4, "AUTO ON EVERY READ", ha="center", fontsize=9, fontweight="bold",
        color=AUTO, family="DejaVu Sans")
ax.text(49, 13.2, "EXPAND", ha="left", fontsize=10.5, fontweight="bold", color=AUTO, family="DejaVu Sans")
ax.text(63, 13.2, "BM25( the read email's own text )  ->  related unread threads",
        ha="left", fontsize=8.7, color=INK)
ax.text(49, 8.2, "NOTE", ha="left", fontsize=10.5, fontweight="bold", color=AUTO, family="DejaVu Sans")
ax.text(63, 8.2, "the thread's key fact  ->  evidence log",
        ha="left", fontsize=8.7, color=INK)

arrow(72, 37, 72, 22, color=AUTO)                    # READ -> auto (down)
ax.text(69.5, 29, "auto", ha="right", fontsize=8.4, color=AUTO)
arrow(79, 22, 79, 37, color=MUT)                     # auto -> READ (up: read one)
ax.text(81.5, 29, "read one", ha="left", fontsize=8.4, color=MUT)

# ---- title + legend -------------------------------------------------------------------------------
ax.text(4, 59, "Find-secrets mailbox agent", fontsize=15.5, fontweight="bold", color=INK,
        family="DejaVu Sans")
leg = [Line2D([0], [0], color=ACC, lw=6, label="tools the model calls"),
       Line2D([0], [0], color=AUTO, lw=6, label="run automatically on every read")]
ax.legend(handles=leg, loc="lower center", bbox_to_anchor=(0.5, -0.04), ncol=2,
          frameon=False, fontsize=9.2, handlelength=1.1)

plt.tight_layout()
os.makedirs("docs", exist_ok=True)
out = "docs/agent_flow.png"
plt.savefig(out, bbox_inches="tight", facecolor=PANEL, dpi=170)
print("wrote", out)
