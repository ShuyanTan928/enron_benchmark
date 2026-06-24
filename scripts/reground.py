"""Re-ground anonymous benchmark items to real Enron identities — the OUTPUT layer.

Generation + blind validation run entirely on anonymous labels (Person A–J, "[firm]") so no
fabricated concealment touches a real identity during generation. This pass runs only when a KEPT
item is saved: Person A–J -> real names (benchmark_pool/people.json, global fixed mapping — Person C
is always Tana Jones), and "[firm]" -> Enron. Counterparty names are already real and untouched.

Field-aware so the result reads like real mail: From/To/Cc headers + the answer key + atoms use the
FULL name (Tana Jones); message subjects/bodies use the FIRST name (greetings, sign-offs, mentions:
"Tana", "Jeff").  (Relies on generation naming everyone as the full label "Person X" — bare single
letters like "H —" are blocked upstream by the letter gate.)
"""
import json
import re
from pathlib import Path

FIRM = {"[firm]": "Enron", "[trading platform]": "Enron Online",
        "[online trading platform]": "Enron Online"}


def name_maps(people_path="benchmark_pool/people.json") -> tuple[dict, dict]:
    people = json.loads(Path(people_path).read_text())["people"]
    full = {p["label"]: p["real_name"] for p in people}
    first = {p["label"]: p["real_name"].split()[0] for p in people}
    return full, first


def reground_text(text: str, m: dict) -> str:
    if not text:
        return text
    for ph, real in FIRM.items():
        text = text.replace(ph, real)
    for lab, nm in m.items():
        text = re.sub(rf"\b{re.escape(lab)}\b", nm, text)
    return text


def _reground_msg(msg: dict, full: dict, first: dict) -> dict:
    out = {**msg}
    if "from" in out:
        out["from"] = reground_text(out["from"], full)
    if "to" in out:
        out["to"] = [reground_text(x, full) for x in (out.get("to") or [])]
    if "cc" in out:
        out["cc"] = [reground_text(x, full) for x in (out.get("cc") or [])]
    if "subject" in out:
        out["subject"] = reground_text(out["subject"], first)
    if "body" in out:
        out["body"] = reground_text(out["body"], first)
    if isinstance(out.get("forward"), dict):
        out["forward"] = _reground_msg(out["forward"], full, first)
    return out


def reground_clues(clues: list, full: dict, first: dict) -> list:
    return [{**c, "messages": [_reground_msg(m, full, first) for m in c.get("messages", [])]}
            for c in clues]


def reground_atoms(atoms: list, full: dict) -> list:
    return [{**a, "fact": reground_text(a.get("fact", ""), full)} for a in atoms]


def answer_from_source(s: dict, full: dict) -> dict:
    t, pl, an = s.get("topic", {}), s.get("plot", {}), s.get("anchor", {})
    return {
        "concealment": reground_text(t.get("secret", ""), full),
        "actor": reground_text(pl.get("actor", ""), full),
        "victim": reground_text(pl.get("victim", ""), full),
        "true_fact": reground_text(pl.get("true_fact", ""), full),
        "false_belief": reground_text(pl.get("false_belief", ""), full),
        "anchor": {"date": (an.get("date", "") or "")[:10], "subject": an.get("subject", "")},
    }


def reground_record(rec: dict, src_entry: dict, full: dict, first: dict) -> dict:
    return {
        "topic_id": rec["topic_id"],
        "status": rec.get("status", "KEPT"),
        "answer": answer_from_source(src_entry, full),
        "atoms": reground_atoms(rec.get("atoms", []), full),
        "clues": reground_clues(rec.get("clues", []), full, first),
    }
