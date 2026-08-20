"""Render the find-secrets agent tool-flow diagram to a PNG for the README (no external SVG tooling)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.lines import Line2D

INK = "#1b2431"; MUT = "#5c6773"; ACC = "#2563eb"; AUTO = "#0d9488"
AUTO_T = "#e7f4f2"; PANEL = "#ffffff"; LINE = "#dce1e8"

fig, ax = plt.subplots(figsize=(11.6, 5.2), dpi=170)
ax.set_xlim(0, 116); ax.set_ylim(0, 55); ax.axis("off")
fig.patch.set_facecolor(PANEL); ax.set_facecolor(PANEL)

def box(x, y, w, h, label, sub=None, edge=ACC, lc=INK, fs=15):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.6,rounding_size=2.2",
                                fc=PANEL, ec=edge, lw=1.8, mutation_aspect=1))
    ax.text(x + w/2, y + h/2 + (2.4 if sub else 0), label, ha="center", va="center",
            fontsize=fs, fontweight="bold", color=lc, family="DejaVu Sans")
    if sub:
        ax.text(x + w/2, y + h/2 - 3.4, sub, ha="center", va="center", fontsize=9.5,
                color=MUT, family="DejaVu Sans")

def arrow(x1, y1, x2, y2, color=MUT, style="-|>", rad=0.0, lw=1.7):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=15,
                                 color=color, lw=lw, connectionstyle=f"arc3,rad={rad}"))

# ---- top row: LIST -> SEARCH <-> READ -> [gate] -> ANSWER --------------------------------------
yT = 33; h = 12
box(4,  yT, 17, h, "LIST",  "orient", edge=ACC)
box(31, yT, 20, h, "SEARCH", "BM25 top-12 · keywords", edge=ACC)
box(61, yT, 17, h, "READ",  "full thread", edge=ACC)
box(96, yT, 18, h, "ANSWER", "found / secret / cites", edge=ACC)

arrow(2, yT+h/2, 4, yT+h/2)                              # enter
arrow(21, yT+h/2, 31, yT+h/2)                            # LIST -> SEARCH
arrow(51, yT+h/2, 61, yT+h/2)                            # SEARCH -> READ
# investigate loop READ -> SEARCH (arc above)
arrow(64, yT+h, 48, yT+h, color=MUT, rad=0.42)
ax.text(56, yT+h+4.6, "investigate loop", ha="center", fontsize=9.5, color=MUT, style="italic")
# READ -> gate -> ANSWER
arrow(78, yT+h/2, 96, yT+h/2)
ax.text(87, yT+h/2+4.2, "floor gate", ha="center", fontsize=9, color=ACC)
ax.text(87, yT+h/2-4.6, "≥ n distinct\nSEARCH / READ", ha="center", va="center",
        fontsize=8.6, color=MUT)

# ---- auto box under READ ------------------------------------------------------------------------
ax.add_patch(FancyBboxPatch((30, 5), 56, 17, boxstyle="round,pad=0.6,rounding_size=2.2",
                            fc=AUTO_T, ec=AUTO, lw=1.5, ls=(0,(5,3)), mutation_aspect=1))
ax.text(58, 18.4, "AUTO ON EVERY READ", ha="center", fontsize=9.2, fontweight="bold",
        color=AUTO, family="DejaVu Sans")
ax.text(33, 13.2, "NOTE", ha="left", fontsize=11, fontweight="bold", color=AUTO, family="DejaVu Sans")
ax.text(46, 13.2, "model writes the thread's key fact  →  evidence log",
        ha="left", fontsize=9.4, color=INK)
ax.text(33, 8.3, "EXPAND", ha="left", fontsize=11, fontweight="bold", color=AUTO, family="DejaVu Sans")
ax.text(49, 8.3, "BM25( the email's own text )  →  8 related threads",
        ha="left", fontsize=9.4, color=INK)

# READ <-> auto box (down = auto, up = read one)
arrow(66, yT, 66, 22, color=AUTO, style="-|>")
ax.text(69.5, 27, "auto", ha="left", fontsize=8.8, color=AUTO)
arrow(73, 22, 73, yT, color=MUT, style="-|>")
ax.text(75.4, 27, "read one", ha="left", fontsize=8.8, color=MUT)

# ---- legend -------------------------------------------------------------------------------------
leg = [Line2D([0],[0], color=ACC, lw=6, label="tools the model chooses"),
       Line2D([0],[0], color=AUTO, lw=6, label="harness runs automatically on every READ")]
ax.legend(handles=leg, loc="lower center", bbox_to_anchor=(0.5, -0.06), ncol=2,
          frameon=False, fontsize=9.5, handlelength=1.1)

ax.text(4, 52.4, "Find-secrets mailbox agent", fontsize=15.5, fontweight="bold", color=INK,
        family="DejaVu Sans")

plt.tight_layout()
out = "docs/agent_flow.png"
import os; os.makedirs("docs", exist_ok=True)
plt.savefig(out, bbox_inches="tight", facecolor=PANEL, dpi=170)
print("wrote", out)
