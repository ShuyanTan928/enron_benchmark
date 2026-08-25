#!/usr/bin/env python3
"""Build a human-audit packet from a benchmark directory.

For every KEPT item it emits one annotation unit that turns the machine AND-check into a task a
person can judge blind:
  A. SUBSET SUFFICIENCY (blind) — for each proper subset of clues, read ONLY those and try to
     recover the concealed fact. PASS wants every subset NOT recoverable.
  B. FULL-SET SUPPORT — reading all clues, do they establish the planted secret?  PASS wants yes.
  C. NATURALNESS — do the emails read like real Enron work mail?
An item PASSES the human audit iff every proper subset is judged insufficient AND the full set
supports the secret. The planted secret is printed AFTER the subset task to limit priming.

Outputs (default results/human_audit/):
  audit_packet.md   — the readable packet with checkboxes, one section per item
  audit_entry.csv   — one blank row per (item) for each annotator to fill; feeds a later kappa calc

Usage:
  uv run python scripts/human_audit_build.py --in-dir benchmark_v2 --out-dir results/human_audit
"""
from __future__ import annotations
import argparse
import csv
import glob
import itertools
import json
from pathlib import Path


def render_msgs(messages: list[dict]) -> str:
    blocks = []
    for m in messages or []:
        to = ", ".join(m.get("to", []) or [])
        cc = ", ".join(m.get("cc", []) or [])
        hdr = f"From: {m.get('from','?')}   To: {to}" + (f"   Cc: {cc}" if cc else "")
        hdr += f"   ({m.get('date','')})\n    Subject: {m.get('subject','')}"
        body = "\n    ".join((m.get("body", "") or "").splitlines())
        blocks.append(f"    {hdr}\n\n    {body}")
    return "\n\n    - - - - -\n\n".join(blocks)


def proper_subsets(n: int):
    """All proper subsets of clue indices 1..n, size 1..n-1, smaller first."""
    idx = list(range(1, n + 1))
    for r in range(1, n):
        for combo in itertools.combinations(idx, r):
            yield list(combo)


def load_kept(in_dir: str):
    items = []
    for path in sorted(glob.glob(str(Path(in_dir) / "emails_*.jsonl"))):
        cfg = Path(path).stem.replace("emails_", "")
        for line in Path(path).read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("status") != "KEPT":
                continue
            r["_config"] = cfg
            items.append(r)
    return items


def build(items, out_dir: str):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    md = ["# Human-audit packet",
          "",
          "For each item: do **Part A first** (do not scroll to the secret), then B and C.",
          "**PASS = every subset in A judged NOT recoverable, AND full set in B supports the secret.**",
          ""]
    rows = []
    for it in items:
        tid = it["topic_id"]
        n = int(it.get("n") or len(it.get("clues", [])))
        cfg = it["_config"]
        mech = it.get("secret_type", "")
        register = "work" if tid.startswith("W") else "casual"
        secret = (it.get("answer") or {}).get("secret", "")
        clues = it.get("clues", [])

        md += [f"\n---\n\n## {cfg} · {tid} · n={n} · {mech} · {register}\n",
               "### The clues (full text)"]
        for c in clues:
            carries = ", ".join(c.get("carries", []))
            md.append(f"\n**[Clue {c.get('i')}]**  _(carries {carries})_\n")
            md.append(render_msgs(c.get("messages")))

        md += ["\n### A. Subset sufficiency — BLIND (do this before reading the secret below)",
               "For each subset, read ONLY those clue(s). Can you state the concealed fact + who "
               "concealed it + who was misled, from them alone?"]
        for sub in proper_subsets(n):
            label = "{" + ",".join(str(x) for x in sub) + "}"
            md.append(f"- clues {label} → recovered?  ` [ ] no `  ` [ ] yes `   reading: __________")

        md += ["\n### B. Full-set support",
               "Read ALL clues together. Do they establish this planted secret?",
               "",
               f"> **PLANTED SECRET:** {secret}",
               "",
               "` [ ] yes, fully supported `   ` [ ] no `",
               "\n### C. Naturalness",
               "Do these read like real Enron work mail (format, tone, length)?",
               "` [ ] yes `   ` [ ] borderline `   ` [ ] no `   notes: __________"]

        rows.append({"config": cfg, "topic_id": tid, "n": n, "mechanism": mech,
                     "register": register, "n_subsets": sum(1 for _ in proper_subsets(n)),
                     "annotator": "", "fullset_supports": "", "all_subsets_insufficient": "",
                     "subsets_that_leaked": "", "natural": "", "pass": "", "notes": ""})

    (out / "audit_packet.md").write_text("\n".join(md))
    with (out / "audit_entry.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"items: {len(items)}")
    print(f"WROTE {out}/audit_packet.md")
    print(f"WROTE {out}/audit_entry.csv  ({len(rows)} blank rows)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-dir", default="benchmark_v2")
    ap.add_argument("--out-dir", default="results/human_audit")
    args = ap.parse_args()
    items = load_kept(args.in_dir)
    if not items:
        raise SystemExit(f"no KEPT items in {args.in_dir}")
    build(items, args.out_dir)


if __name__ == "__main__":
    main()
