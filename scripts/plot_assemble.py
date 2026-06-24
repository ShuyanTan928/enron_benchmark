"""Assemble the Step 2 prompt for one or all topics (new schema).

Fills prompts/secret_plot_from_carrier.md with:
  - SECRET   : the abstract binary secret (name / secret / either_or, from topics_v2.json)
  - ANCHOR   : the topic's real enron_anchor email — its FULL substantive body, pulled from
               the corpus by message_id, with the 10 mailbox people relabeled to Person A–J
               and the company name scrubbed
  - WIDER TEAM: the anonymous roster + authority graph (from people.json)

Output: prompts/plot/<TID>.txt — paste-ready, no real names of the 10, no company name.

Usage:
  uv run python scripts/plot_assemble.py                 # all topics
  uv run python scripts/plot_assemble.py --topic T05     # one
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.grounding.corpus import load_emails


def make_relabel(people):
    """Relabel the 10 cast names -> Person labels without corrupting same-name strangers
    (e.g. 'Mark Holsworth' must NOT become 'Person E Holsworth'). A bare cast first name
    followed by a capitalized non-'Person' word is left alone, because 'Sara Tanya' (signature
    + stranger) is structurally identical to 'Jeff Nogid' (a real stranger sharing a cast first
    name) — relabeling would misattribute the stranger. Those residual signature leaks are
    tolerated (strangers are tolerated); the company name is the hard line and is scrubbed separately."""
    full_map, first_map, last_map = {}, {}, {}
    for p in people:
        parts = p["real_name"].split()
        full_map[p["real_name"]] = p["label"]
        first_map[parts[0]] = p["label"]
        last_map[parts[-1]] = p["label"]
    # signature variants of two-part cast names carrying a middle particle ('Carol St. Clair')
    for p in people:
        parts = p["real_name"].split()
        if len(parts) == 2:
            full_map[f"{parts[0]} St. {parts[1]}"] = p["label"]
            full_map[f"{parts[0]} St {parts[1]}"] = p["label"]

    def relabel(s):
        s = s or ""
        # 1) full names + variants first (longest first)
        for fn in sorted(full_map, key=len, reverse=True):
            s = re.sub(r"\b" + re.escape(fn) + r"\b", full_map[fn], s)
        # 2) bare first name. Relabel when it sits right before an already-relabeled 'Person X'
        #    placeholder (a signature next to a header we just relabeled), or when NOT followed by
        #    a capitalized word (orig rule). Stays put before a capitalized stranger surname.
        for fn in sorted(first_map, key=len, reverse=True):
            lab = first_map[fn]
            s = re.sub(r"\b" + re.escape(fn) + r"\b(?=\s+Person\b)", lab, s)
            s = re.sub(r"\b" + re.escape(fn) + r"\b(?!\s+[A-Z])", lab, s)
        # 3) bare last name — only when standalone (no capitalized word right before it)
        for ln in sorted(last_map, key=len, reverse=True):
            lab = last_map[ln]
            s = re.sub(r"([A-Z][a-z]+\s+)?\b" + re.escape(ln) + r"\b",
                       (lambda lab: lambda m: m.group(0) if m.group(1) else lab)(lab), s)
        return s
    return relabel


def scrub_corp(s: str) -> str:
    """Anonymize the real company to a bracketed placeholder. Idempotent: catches the raw
    names AND the prose forms ('the firm') that earlier scrubbing/generation may have baked in,
    so re-assembly always converges to [firm] regardless of what the source files hold."""
    s = re.sub(r"\bEnron\s*Online\b", "[trading platform]", s, flags=re.I)
    s = re.sub(r"\bEnron North America\b", "[firm]", s, flags=re.I)
    s = re.sub(r"\bECT(RIC)?\b", "[firm]", s)
    s = re.sub(r"\bENA\b", "[firm]", s)
    s = re.sub(r"\bEOL\b", "[trading platform]", s)
    s = re.sub(r"\bEnron\b", "[firm]", s, flags=re.I)
    s = re.sub(r"\bthe online trading platform\b", "[trading platform]", s, flags=re.I)
    s = re.sub(r"\bthe firm\b", "[firm]", s, flags=re.I)
    return s


def load_plot_secrets(path):
    """{topic_id: plot_dict} — accepts the plot-generation file (top-level 'kept', each with a
    'plot' sub-dict) or a flat jsonl where every line is already a plot dict."""
    p = Path(path)
    txt = p.read_text()
    if p.suffix == ".json":
        d = json.loads(txt)
        if isinstance(d, dict) and "kept" in d:
            return {k["plot"]["topic_id"]: k["plot"] for k in d["kept"]}
    return {json.loads(l)["topic_id"]: json.loads(l) for l in txt.splitlines() if l.strip()}


def load_plot_topics(path):
    """{topic_id: {secret, either_or, era}} — accepts the plot-generation file (kept[].topic +
    kept[].anchor.date) or the old topics_v2.json ({'topics':[{id, secret, either_or,
    enron_anchor.date}]})."""
    d = json.loads(Path(path).read_text())
    out = {}
    if isinstance(d, dict) and "kept" in d:
        for k in d["kept"]:
            t, a = k.get("topic", {}), k.get("anchor", {})
            out[t.get("id")] = {"secret": t.get("secret", ""), "either_or": t.get("either_or", ""),
                                "era": (a.get("date", "") or "")[:10]}
    else:
        for t in d.get("topics", []):
            out[t["id"]] = {"secret": t.get("secret", ""), "either_or": t.get("either_or", ""),
                            "era": ((t.get("enron_anchor") or {}).get("date", "") or "")[:10]}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default="all", help="topic id (e.g. T05) or 'all'")
    ap.add_argument("--topics", default="benchmark_pool/topics_v2.json")
    ap.add_argument("--outdir", default="prompts/plot")
    args = ap.parse_args()

    topics = json.loads(Path(args.topics).read_text())["topics"]
    people = json.loads(Path("benchmark_pool/people.json").read_text())
    P, AUTH = people["people"], people["authority"]
    relabel = make_relabel(P)
    template = Path("prompts/secret_plot_from_carrier.md").read_text()

    # full cleaned bodies, keyed by message_id, for richer grounding than the 400-char snippet
    body_by_id = {e.message_id: e for e in load_emails()}

    team = "\n".join(
        ["Team:"] + [f"- {p['label']} — {p['role']}" for p in P]
        + ["", "Authority:"] + [f"- {e['from']} {e['rel']} {e['to']}" for e in AUTH]
    )

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    ids = [t["id"] for t in topics] if args.topic == "all" else [args.topic]
    tmap = {t["id"]: t for t in topics}

    print(f"{'topic':5} {'leak':4}  file")
    for tid in ids:
        t = tmap[tid]
        topic_json = json.dumps(
            {"id": t["id"], "name": t["name"], "secret": t["secret"], "either_or": t["either_or"]},
            indent=2, ensure_ascii=False)

        a = t["enron_anchor"]
        em = body_by_id.get(a["message_id"])
        full_body = em.body if em else a.get("snippet", "")
        frm = relabel(a["from"])
        to = ", ".join(relabel(x) for x in a.get("to", [])) or "(internal)"
        anchor_block = (
            f'From: {frm}  →  To: {to}   ({a["date"][:10]})\n'
            f'Subject: "{relabel(a["subject"])}"\n\n'
            f'{relabel(full_body)}'
        )

        out = (template.replace("<<TOPIC>>", topic_json)
                       .replace("<<ANCHOR>>", anchor_block)
                       .replace("<<RELATIONSHIPS>>", team)
                       .replace("<<TID>>", tid))
        out = scrub_corp(out)

        leaks = set()
        for p in P:
            for v in {p["real_name"], p["real_name"].split()[0], p["real_name"].split()[-1]}:
                if re.search(r"\b" + re.escape(v) + r"\b", out):
                    leaks.add(v)
        if re.search(r"\benron\b", out, re.I):
            leaks.add("enron")

        fp = outdir / f"{tid}.txt"
        fp.write_text(out)
        print(f"{tid:5} {'FAIL' if leaks else 'PASS':4}  {fp}"
              + (f"  LEAK={sorted(leaks)}" if leaks else ""))


if __name__ == "__main__":
    main()
