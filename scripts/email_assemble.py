"""Assemble the Step 3 clue-distribution prompt for one or all Step 2 secrets.

Fills prompts/clue_emails_from_plot.md with each secret's binary (true_fact / false_belief /
either_or) + the Step 2 plot + answer key + the team roster → prompts/step3/<TID>.txt.
Reuses scrub_corp so the company is never named in the prompt.

Usage:
  uv run python scripts/email_assemble.py                 # all secrets in step2_lean.jsonl
  uv run python scripts/email_assemble.py --topic T07
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))      # for plot_assemble helpers
from plot_assemble import scrub_corp, make_relabel, load_plot_secrets, load_plot_topics


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default="all", help="topic id (e.g. T07) or 'all'")
    ap.add_argument("--n", type=int, default=2, help="number of clue emails to split into")
    ap.add_argument("--secrets", default="benchmark_pool/plot_generation.json")
    ap.add_argument("--topics", default="benchmark_pool/plot_generation.json")
    ap.add_argument("--outdir", default="prompts/step3")
    args = ap.parse_args()

    smap = load_plot_secrets(args.secrets)
    tmap = load_plot_topics(args.topics)
    people = json.loads(Path("benchmark_pool/people.json").read_text())
    P, AUTH = people["people"], people["authority"]
    template = Path("prompts/clue_emails_from_plot.md").read_text()
    relabel = make_relabel(P)

    def voice_card(p):
        """The person's real writing-style persona_card, with real names relabeled to
        Person labels and the company scrubbed. '' if no profile on disk."""
        pf = Path("profiles") / (p["real_name"].lower().replace(" ", ".") + ".json")
        if not pf.exists():
            return ""
        card = json.loads(pf.read_text()).get("persona_card", "")
        return relabel(scrub_corp(card)).strip()

    # Lean roster only — voice/tone is applied in the separate Step-3 voice pass, not here.
    team_parts = [f"- {p['label']} — {p['role']}" for p in P]
    team_parts += ["", "Authority:"] + [f"- {e['from']} {e['rel']} {e['to']}" for e in AUTH]
    team = "\n".join(team_parts)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    ids = list(smap) if args.topic == "all" else [args.topic]

    print(f"{'topic':5} {'leak':4}  file")
    for tid in ids:
        s = smap[tid]
        t = tmap.get(tid, {})
        era = t.get("era") or "the period of the original events"
        secret_block = (
            f"the concealment:                    {t.get('secret', '')}\n"
            f"what is actually true:              {s['true_fact']}\n"
            f"what the victim is led to believe:  {s['false_belief']}\n"
            f"either / or:                        {t.get('either_or', '')}")
        out = (template.replace("<<SECRET>>", secret_block)
                       .replace("<<ACTOR>>", s["actor"])
                       .replace("<<VICTIM>>", s["victim"])
                       .replace("<<PLOT>>", s["plot"])
                       .replace("<<TEAM>>", team)
                       .replace("<<TID>>", tid)
                       .replace("<<ERA>>", era)
                       .replace("<<N>>", str(args.n)))
        out = scrub_corp(out)

        leak = "FAIL" if re.search(r"\benron\b", out, re.I) else "PASS"
        fp = outdir / f"{tid}.txt"
        fp.write_text(out)
        print(f"{tid:5} {leak:4}  {fp}")


if __name__ == "__main__":
    main()
