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


def _label_pat(label: str) -> str:
    """Every way a generator writes the label "Person D" — including the ones it invents when it needs
    a token rather than a name: an email local part (personD@…), a slug (person_d), a run-on (PersonD).
    Matching only the canonical spelling left those in the shipped mail, spelling out the anonymisation."""
    letter = label.split()[-1]
    return rf"\bperson[\s_-]*{re.escape(letter)}\b"


# A bare capital A-J after one of these is a document part, not a person: leave "Plan B", "Exhibit A".
_NON_PERSON_BEFORE = re.compile(
    r"\b(?:plan|exhibit|section|schedule|part|phase|option|type|class|grade|appendix|annex|clause|"
    r"figure|table|item|note|tier|group|category|model|series|version|round|level|column|track|"
    r"attachment|addendum|building|gate|route|line|form)\s+$", re.IGNORECASE)


def _reground_bare_labels(text: str, m: dict) -> str:
    """A generator sometimes writes a bare single letter ('candidate J', "J's record") instead of the
    full label 'Person J'; the person[...] pattern misses those. Catch a bare A-J only in a clear person
    context (possessive, 'candidate X', a title), and only for letters that are real labels."""
    letter = {lab.split()[-1].upper(): nm for lab, nm in m.items()}

    def poss(mo):
        L = mo.group(1)
        if L not in letter or _NON_PERSON_BEFORE.search(text[:mo.start()]):
            return mo.group(0)
        return f"{letter[L]}'s"

    def ctx(mo):
        pre, L = mo.group(1), mo.group(2)
        return f"{pre}{letter[L]}" if L in letter else mo.group(0)

    def suffix(mo):
        L = mo.group(1)
        return f"{letter[L]}{mo.group(2)}" if L in letter else mo.group(0)

    text = re.sub(r"\b([A-J])'s\b", poss, text)
    text = re.sub(r"\b(candidate\s+|Mr\.?\s+|Mrs\.?\s+|Ms\.?\s+|Dr\.?\s+)([A-J])\b", ctx, text)
    text = re.sub(r"\b([A-J])(\s+candidacy\b)", suffix, text)   # 'J candidacy' -> 'Susan candidacy'
    return text


def bare_labels_left(text: str) -> list:
    """Person-context bare labels still present after regrounding — a guard for the save path. Skips the
    document-part possessives ('Plan B's') that regrounding correctly leaves alone."""
    if not text:
        return []
    hits = [mo.group(0) for mo in re.finditer(r"\b[A-J]'s\b", text)
            if not _NON_PERSON_BEFORE.search(text[:mo.start()])]
    hits += re.findall(r"\bcandidate\s+[A-J]\b|\b(?:Mr|Mrs|Ms|Dr)\.?\s+[A-J]\b|\b[A-J]\s+candidacy\b", text)
    return hits


def reground_text(text: str, m: dict) -> str:
    if not text:
        return text
    for ph, real in FIRM.items():
        text = text.replace(ph, real)
    for lab, nm in m.items():
        pat = _label_pat(lab)
        # An address needs a local part, not a name: personD@x -> carol.clair@x, never "Carol Clair@x".
        text = re.sub(pat + r"(?=@)", nm.lower().replace(" ", "."), text, flags=re.IGNORECASE)
        text = re.sub(pat, nm, text, flags=re.IGNORECASE)
    return _reground_bare_labels(text, m)


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
    return [{**c,
             **({"plot": reground_text(c["plot"], full)} if c.get("plot") else {}),
             "messages": [_reground_msg(m, full, first) for m in c.get("messages", [])]}
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
