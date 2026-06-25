"""Build a human-readable Step 3 file: each topic's SECRET summary + its clue emails.

Pairs a Step 3 clues file (email_generate output, *.jsonl) with the Gen-4 source
(gen4_*.json, which carries the secret summary / answer key) so the reader sees, per topic:
  - the one-paragraph secret (concealment), the either/or, true vs false belief, actor->victim
  - then each clue: what it carries + the actual email(s).

Usage:
  uv run python scripts/email_readable.py --clues benchmark_pool/gen4_step3_clues.jsonl \
      --source benchmark_pool/gen4_sonnet.json --out benchmark_pool/gen4_step3_clues.txt
"""
import argparse
import json
from pathlib import Path


def render_clue(c: dict) -> str:
    out = [f"  CLUE {c.get('i')}"]
    for m in c.get("messages", []):
        to = ", ".join(m.get("to", []) or [])
        cc = ", ".join(m.get("cc", []) or [])
        out.append(f"    From: {m.get('from')}   To: {to}" + (f"   Cc: {cc}" if cc else "")
                   + f"   ({m.get('date', '')})")
        out.append(f"    Subject: {m.get('subject', '')}")
        for ln in (m.get("body", "") or "").split("\n"):
            out.append(f"      {ln}")
        out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clues", default="benchmark_pool/gen4_step3_clues.jsonl")
    ap.add_argument("--source", default="benchmark_pool/gen4_sonnet.json",
                    help="Gen-4 output holding the secret summary / answer key")
    ap.add_argument("--out", default="benchmark_pool/gen4_step3_clues.txt")
    args = ap.parse_args()

    kept = [json.loads(l) for l in Path(args.clues).read_text().splitlines() if l.strip()]
    src = {k["id"]: k for k in json.loads(Path(args.source).read_text())["kept"]}

    lines = [f"Step 3 — clue breakdown ({len(kept)} topic(s)); each block: SECRET then its clue emails", ""]
    for k in kept:
        tid = k["topic_id"]
        s = src.get(tid, {})
        t = s.get("topic", {})
        pl = s.get("plot", {})
        a = s.get("anchor", {})
        ans = k.get("answer") or {}                       # regrounded answer key when present
        anc = ans.get("anchor") or a
        lines += [
            "=" * 90,
            f"{tid}  «{t.get('name', '')}»   [{k.get('status', 'KEPT')}]",
            "",
            "  --- THE SECRET (answer key) ---",
            f"  concealment : {ans.get('concealment') or t.get('secret', '')}",
            f"  true_fact   : {ans.get('true_fact') or pl.get('true_fact', '')}",
            f"  false_belief: {ans.get('false_belief') or pl.get('false_belief', '')}",
            f"  actor       : {ans.get('actor') or pl.get('actor', '')}",
            f"  victim      : {ans.get('victim') or pl.get('victim', '')}",
            f"  anchor      : {(anc.get('date', '') or '')[:10]}  \"{anc.get('subject', '')}\"",
            "",
        ]
        atoms = k.get("atoms") or []
        if atoms:
            lines.append(f"  --- ATOMS ({len(atoms)}): role · carrier ---")
            for a in atoms:
                lines.append(f"    {a.get('id')} [{a.get('role')} · via {a.get('carrier', 'body')}] "
                             f"{a.get('fact', '')}")
            lines.append("")
        lines.append("  --- THE CLUES (what the benchmark shows the model) ---")
        for c in k.get("clues", []):
            lines.append(render_clue(c))
        lines.append("")
    Path(args.out).write_text("\n".join(lines))
    print(f"WROTE {args.out}  ({len(kept)} topic(s): {', '.join(k['topic_id'] for k in kept)})")


if __name__ == "__main__":
    main()
