#!/usr/bin/env python3
"""Spec-driven email generation — the upgraded architecture (lying).

  [1] topic + anchor  -> ATOMS: three clean facts a1 (truth F) / a2 (actor knows F) / a3 (false line)
        -> atom judge (faithful + clean a1/a2/a3 + decomposable); iterate     (prompts/spec_*_lying.md)
  [2] plan_distribution(atoms, n): fixed n=2/3/4 template -> which atom(s) each clue carries
  [3a] atoms + plan -> ONE observable PLOT per clue (merge/split)             (prompts/clue_plot_min.md)
  [3b] plots + voice -> clue emails written in each sender's own hand         (prompts/clue_email_min.md)
  [4] AND check (subset test) + diagnose; iterate the email step             (reused: email_generate)
  [5] reground KEPT items to real Enron identities at save                   (reused: reground)

The atoms replace the old monolithic plot + separate atomize. They are clean and CARRIER-FREE: a1 =
the truth F, a2 = "actor knows F" (no observable form chosen yet), a3 = the false line. The conclusion
lives ONLY in answer_key; how each atom becomes observable is decided at the render step, so leaks are
prevented by construction and the AND check confirms rather than filters.

n = total clue count (the user's instruction). plan_distribution applies FIXED templates that say
which atom(s) each clue carries; the render step (n-aware) turns each clue's atom(s) into ONE
observable scene — MERGING atoms that share a clue (n=2: a1+a2 = the record sent to the actor) and
SPLITTING a1 into a1.1/a1.2 (n=4). a1 and a3 never share a clue.
  n=2 : c1={a1, a2}   c2={a3}
  n=3 : c1={a1}  c2={a2}  c3={a3}
  n=4 : c1={a1.1}  c2={a1.2}  c3={a2}  c4={a3}
Only n=2/3/4 are supported. Whether a1 can split into two innocuous halves (for n=4) is decided by
the AND-check, not pre-computed.

  uv run python scripts/atomize_build.py --topic T02 --n 3
  uv run python scripts/atomize_build.py --topic all --n 2 --budgets 3,5
"""
from __future__ import annotations
import argparse
import json
import random
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, "scripts")
sys.path.insert(0, ".")
from plot_assemble import make_relabel, scrub_corp                                   # noqa: E402
from email_generate import (extract_json, render, build_team, validate, diagnose)    # noqa: E402

from reground import name_maps, reground_clues, reground_text, FIRM                   # noqa: E402
from src.models.engine_factory import build_engine                                   # noqa: E402
from src.grounding.prompts import CONCEALMENT_ACTS, resolve_type                       # noqa: E402

CLUE_PLOT = Path("prompts/clue_plot_min.md")  # [3a] atoms+plan -> observable scene (plot) per clue
CLUE_EMAIL = Path("prompts/clue_email_min.md")  # [3b] plots+voice -> real emails in each sender's hand (min)
STYLE_BANK = Path("benchmark_pool/style_bank.json")
ACK_BANK = Path("benchmark_pool/ack_bank.json")  # real terse Enron receipt replies, mined from the corpus
FILE_BANK = Path("benchmark_pool/file_bank.json")  # real Enron attachment filenames, mined from the corpus
_BANK = None
_ACKS = None
_FILES = None


def _rand_ack() -> str:
    """A real terse receipt reply pulled from the Enron corpus (benchmark_pool/ack_bank.json). Randomised
    per call so the a2 example never fixes one phrase — the SURFACE varies, killing the 'received and
    noted' clone. Falls back to a plain 'got it.' if the bank is missing."""
    global _ACKS
    if _ACKS is None:
        _ACKS = json.loads(ACK_BANK.read_text()) if ACK_BANK.exists() else ["got it."]
    return random.choice(_ACKS) if _ACKS else "got it."


# the synthetic "CP&L-CRED-2001-05" code format never appears in the real corpus; Enron named files
# descriptively (words, often a date, a .doc/.xls/.pdf). _rand_file() draws a real one from the bank;
# _realize_refs() swaps every leftover synthetic code in an example for a real filename (same code ->
# same file within an example, so the shared handle stays consistent).
_SYN_REF = re.compile(r"[A-Z][A-Z&]*(?:-[A-Z0-9]+){2,}")


def _rand_file() -> str:
    """A real Enron attachment filename, pulled from the corpus-mined bank (benchmark_pool/file_bank.json)
    — descriptive words, often a date, a .doc/.xls/.pdf. Never an invented letter-code."""
    global _FILES
    if _FILES is None:
        _FILES = json.loads(FILE_BANK.read_text()) if FILE_BANK.exists() else ["Daily Settles.xls"]
    return random.choice(_FILES) if _FILES else "Daily Settles.xls"


def _realize_refs(ex: str) -> str:
    seen = {}
    for code in _SYN_REF.findall(ex):
        if any(ch.isdigit() for ch in code) and code not in seen:  # digit-guard skips e.g. HOW-TO-FIX
            seen[code] = _rand_file()
    for code, fname in seen.items():
        ex = ex.replace(f"ref {code}", fname).replace(code, fname)
    return ex


def _act(secret_type: str) -> dict:
    """The per-type concealing-act descriptor (a3). commission/omission/paltering come from the shared
    CONCEALMENT_ACTS; any other type (lying, casual) falls back to commission's false-statement act."""
    return CONCEALMENT_ACTS.get(secret_type) or CONCEALMENT_ACTS["commission"]


def atomize_paths(register: str, mechanism: str):
    """ONE atoms template for all six cells — the register and the a3 act arrive as slots.

    work x commission used to fork to its own tuned pair, for one reason: that pair handled the timing-gap
    "it must have changed in between" escape and the shared template did not. The shared one handles it
    now, so the fork bought nothing and cost plenty — every fix had to be applied twice, and when one was
    missed the fork silently drifted (it went on demanding that a1 name the dated record it rests on, long
    after atoms went carrier-free)."""
    return (Path("prompts/atomize_min.md"), None)   # min: example-driven, no judge


def _checks(v: dict) -> list:
    """All check entries (a dict carrying a 'verdict') in a judge verdict — type-agnostic, so each
    secret_type's judge may declare its own check set."""
    return [(k, val) for k, val in (v or {}).items()
            if isinstance(val, dict) and "verdict" in val]


def _anchor_block(entry: dict, relabel) -> str:
    a = entry.get("anchor") or {}          # casual/ungrounded topics have no anchor
    if not a:
        return "(no anchor — casual secret; invent the concrete specifics from the SECRET above)"
    body = entry.get("anchor_full_body") or a.get("snippet", "")
    to = ", ".join(relabel(x) for x in a.get("to", [])) or "(internal)"
    return (f'From: {relabel(a["from"])}  ->  To: {to}   ({(a.get("date", "") or "")[:10]})\n'
            f'Subject: "{relabel(a.get("subject", ""))}"\n\n{relabel(body)}')


def _pass(v) -> bool:
    """Only a FAIL sinks an atoms record. WEAK means "it holds, but not the strongest version" — an
    eight-check conjunctive gate that also rejects on WEAK is a perfectionist: it threw away records whose
    other seven checks were clean, and burned the retry budget re-rolling ones already fine."""
    chk = _checks(v)
    return bool(chk) and not any(val.get("verdict", "").upper() == "FAIL" for _, val in chk)


def _feedback_checks(v, what) -> str:
    lines = [f"- {k} [{val.get('verdict')}]: {val.get('reason', '')}"
             for k, val in _checks(v) if val.get("verdict", "").upper() == "FAIL"]
    return (f"Prior {what} failed review:\n" + "\n".join(lines)
            + (f"\nFIX: {v.get('fix', '')}" if v.get("fix") else "")
            + f"\nReturn ONE corrected {what} JSON, nothing else.")


# ------------------------------------------------------------------- [1] atoms generate + judge
# Topics come from STAGE 1 secret-first grounding (scripts/ground_topics.py --secret-type lying →
# topics_lying.json); this runner reads them via --plots and decomposes each into a SPEC.
# One worked atom set per cell, filled into atomize_min's <<EXAMPLE>> (omission blank until run).
ATOMIZE_EXAMPLES = {
"work_commission": '''Secret: an ops lead hides from the scheduler that a transport permit lapsed, and tells them it's active, so the scheduler keeps booking against it.
  a1: "The Line 300 interruptible-transport permit is lapsed and not in force."
  a2: "Person D knows the Line 300 transport permit is lapsed and not in force."
  a3: "Person D tells Person G the Line 300 permit is active and cleared to schedule against."''',
"casual_commission": '''Secret: a colleague hides from a coworker that a mutual friend was fired for stealing, and says they left on good terms, so the coworker brings them in.
  a1: "The mutual friend was fired from their last job for stealing company money."
  a2: "Person A knows the mutual friend was fired for stealing company money."
  a3: "Person A tells Person C the friend left that job on their own and on good terms."''',
"work_paltering": '''Secret: a coordinator hides from the desk that a counterparty was downgraded below the credit threshold, by pointing to its standing credit-line approval without mentioning the downgrade.
  a1: "The counterparty's credit rating has fallen below the threshold the line requires."
  a2: "Person C knows the counterparty's rating has fallen below the threshold."
  a3: "Person C points Person D to the counterparty's standing credit-line approval on file, without mentioning the downgrade, so D treats the line as good."''',
"casual_paltering": '''Secret: a colleague hides from a coworker that a mutual friend defaulted on a loan now in collections, by saying they just paid off their car loan in full.
  a1: "The mutual friend defaulted on a $40,000 bank loan and it went to collections."
  a2: "Person J knows the mutual friend defaulted on the loan and it went to collections."
  a3: "Person J tells Person C the friend just paid off their car loan in full last month."''',
"work_omission": '''Secret: an ops lead hides from the scheduler that a transport permit lapsed, by sending them the Line 300 status with the lapse left out, so the scheduler keeps booking against it.
  a1: "The Line 300 interruptible-transport permit is lapsed and not in force."
  a2: "Person D knows the Line 300 transport permit is lapsed and not in force."
  a3: "Person D sends Person G the Line 300 weekly scheduling status — nominations, capacity, timing — with the permit's lapse left out."''',
"casual_omission": '''Secret: a colleague hides from a coworker that a mutual friend was fired for stealing, by giving them a rundown on the friend that leaves the firing out, so the coworker brings them in.
  a1: "The mutual friend was fired from their last job for stealing company money."
  a2: "Person A knows the mutual friend was fired for stealing company money."
  a3: "Person A sends Person C a rundown on the friend for the role — prior roles, availability — with the firing for stealing left out."''',
}


def build_atomize_prompt(entry: dict, relabel, team: str, gen_path: Path,
                      register: str = "casual", mechanism: str = "commission") -> str:
    t = entry["topic"]
    # `act` is the concealing act the Step-1 gate actually vetted. Carry it across the boundary, or a3
    # is re-invented here and the vetted act — a paltering lever above all — silently drifts.
    topic_json = json.dumps({"id": entry["id"], "name": t.get("name", ""),
                             "secret": t.get("secret", ""), "true_fact": t.get("true_fact", ""),
                             "false_belief": t.get("false_belief", ""), "act": t.get("act", "")},
                            indent=2, ensure_ascii=False)
    act = _act(mechanism)
    tmpl = gen_path.read_text()
    if register == "work":
        # A dateless corpus email parses to 1980-01-01; don't let that bogus date become the era.
        adate = (entry.get("anchor") or {}).get("date", "")[:7]
        anchor, era = _anchor_block(entry, relabel), (adate if adate >= "1999" else "a month in 2000-2001")
    else:                                                      # casual: no anchor — drop the section
        tmpl = tmpl.replace("## Anchor — the real email this work secret sits on\n<<ANCHOR>>\n\n", "")
        anchor, era = "", "a month in 2000-2001"
    return scrub_corp(tmpl
                      .replace("<<TOPIC>>", topic_json).replace("<<ANCHOR>>", anchor)
                      .replace("<<RELATIONSHIPS>>", team).replace("<<TID>>", entry["id"])
                      .replace("<<TYPE>>", mechanism).replace("<<ACT_NAME>>", act["label"])
                      .replace("<<A3_ACT>>", act["render"]).replace("<<A3_ROLE>>", act["a3_role"])
                      .replace("<<EXAMPLE>>", ATOMIZE_EXAMPLES.get(f"{register}_{mechanism}", ""))
                      .replace("<<ERA_NOTE>>", era))


def make_atoms(gen, jud, entry, relabel, team, max_iters, temp, secret_type="commission"):
    """Generate the atoms — NO judge. The prompt is example-driven (atomize_min), so quality is built
    into generation rather than gated after; only re-ask on a parse miss. `jud` is unused (kept for the
    caller's signature). Returns (atoms|None, None, log)."""
    register, mechanism = resolve_type(entry.get("category", "casual"), secret_type)
    gen_path, _ = atomize_paths(register, mechanism)
    base = build_atomize_prompt(entry, relabel, team, gen_path, register, mechanism)
    prompt, log = base, []
    for it in range(1, max_iters + 1):
        cand = extract_json(gen.generate(prompt, max_tokens=2600, temperature=temp)[0])
        if cand and cand.get("a1") and cand.get("a3"):
            cand["register"] = register        # carried so plot picks the per-cell example
            log.append({"iter": it, "result": "ok"})
            return cand, None, log
        log.append({"iter": it, "result": "parse_fail"})
        prompt = base + "\n\n## CORRECTION\nReturn ONLY the JSON object, with a1/a2/a3."
    return None, None, log


# ------------------------------------------------------------------- [2] plan the distribution
# Atoms are exactly a1 (the whole truth), a2 (actor knows), a3 (false line). n = total clue count,
# set by the user. Splitting a1 into a1.1/a1.2 happens HERE (only at n=4), per the FIXED templates —
# the SPEC does NOT pre-split a1. Whether a1 can actually split into two innocuous halves is decided
# downstream by the AND-check, not pre-computed.
TEMPLATES = {
    2: [["a1", "a2"], ["a3"]],
    3: [["a1"], ["a2"], ["a3"]],
    4: [["a1.1"], ["a1.2"], ["a2"], ["a3"]],
}


def plan_distribution(atoms: dict, n: int):
    """Fixed clue->atom assignment per the user's n=2/3/4 templates. Returns (plan|None, err)."""
    tmpl = TEMPLATES.get(n)
    if tmpl is None:
        return None, f"n={n} unsupported (templates are n=2, 3, 4)"
    plan = []
    for carries in tmpl:
        c = {"i": len(plan) + 1, "carries": list(carries)}
        if "a3" in carries:
            c["reliance"] = True
        plan.append(c)
    return plan, None


def _atom_index(atoms: dict) -> dict:
    return {
        "a1": {"role": atoms["a1"].get("role", "true_state"), "fact": atoms["a1"].get("fact", "")},
        "a2": {"role": atoms["a2"].get("role", "knew"), "fact": atoms["a2"].get("fact", "")},
        # a3's role is the concealing act — false_statement / withheld_disclosure / misleading_truth
        "a3": {"role": atoms["a3"].get("role", "false_statement"), "fact": atoms["a3"].get("fact", "")},
    }


def assignment_block(atoms: dict, plan: list) -> str:
    idx, lines = _atom_index(atoms), []
    split = any(cid in ("a1.1", "a1.2") for c in plan for cid in c["carries"])
    for c in plan:
        merge = " (merge into one observation)" if len(c["carries"]) > 1 else ""
        lines.append(f"clue {c['i']} — carries {', '.join(c['carries'])}{merge}")
        for cid in c["carries"]:
            if cid in ("a1.1", "a1.2"):
                half = "first" if cid == "a1.1" else "second"
                lines.append(f"    {cid} = the {half} half of a1 (split a1; see below)")
            else:
                a = idx.get(cid, {})
                lines.append(f"    {cid} [{a.get('role', '')}] {a.get('fact', '')}")
        if c.get("reliance"):
            rule = atoms.get("reliance_rule", "")
            lines.append("    + reliance here (2-msg thread, victim replies acting on it)"
                         + (f": {rule}" if rule else ""))
    lines.append("no clue may reveal another clue's atom.")
    if split:
        lines.append(f"\na1 (the full truth, split across a1.1 and a1.2): {idx['a1']['fact']}")
        lines.append("  each half innocuous alone (neither reveals the truth); together they recover a1.")
    return "\n".join(lines)


def flatten_atoms(atoms: dict) -> list:
    """Flat list for storage / regrounding: the three atoms a1, a2, a3."""
    idx = _atom_index(atoms)
    return [{"id": k, **idx[k]} for k in ("a1", "a2", "a3")]


# ------------------------------------------------------------------- [3] render clues (one call)
def voices_block(atoms: dict) -> str:
    global _BANK
    if _BANK is None:
        _BANK = json.loads(STYLE_BANK.read_text()) if STYLE_BANK.exists() else {}
    text = " ".join(str(atoms.get(k, "")) for k in ("actor", "victim", "casting_note"))
    text += " " + " ".join(atoms.get(k, {}).get("fact", "") for k in ("a1", "a2", "a3"))
    labels = set(re.findall(r"Person [A-J]", text))
    use = [l for l in _BANK if l in labels] or list(_BANK)
    return "\n\n".join(f"{lab} — {(_BANK[lab].get('card') or '').strip()}" for lab in use) \
        or "(no voice samples available)"


def _matter(p: str, atoms: dict) -> str:
    # <<A3_ACT>>: this mechanism's DEFINITION, spliced INLINE where a3 is named — no separate block.
    # One line each (Rogers et al.'s commission / omission / paltering, plus the constraints this
    # benchmark needs). It defines the ACT only; clue structure is the prompts' own business.
    act = _act(atoms.get("secret_type", "commission"))
    return (p.replace("<<A3_ACT>>", act["render"])
            .replace("<<ACTOR>>", atoms["actor"]).replace("<<VICTIM>>", atoms["victim"])
            .replace("<<COUNTERPARTY>>", atoms.get("counterparty", "the counterparty"))
            .replace("<<MATTER>>", atoms.get("matter", "")))


# The AND logic is stated HERE, not in the atom block — and its correct statement DIFFERS by n:
#   n=2  a1+a2 MERGED into one clue → the ACTOR MUST be on the truth clue (their receipt IS a2).
#   n=3  a1 / a2 / a3 one each      → the ACTOR must NOT be on the truth clue, or truth+act leaks.
#   n=4  a1 SPLIT into a1.1/a1.2    → same, and the truth itself is halved across two clues.
# Injecting all three, hedged with "if", is what confused the model; inject only the one that applies.
SEPARATION_N2 = """\
## your 2 clues are an and-gate
neither alone gives the concealment — only both together. the a1+a2 clue reads as an ordinary record or
thread reaching someone; the a3 clue as an ordinary message.
casting: the actor is on the a1+a2 clue — its recipient, named on the record, or on the thread that
carries the truth; that presence is a2. the victim is not on it — a victim who sees the truth isn't
misled. (the person the fact is about may be named, need not receive it.)"""

SEPARATION_N3 = """\
## your 3 clues are an and-gate
only a2 carries the actor's knowing — so no clue alone and no pair gives the secret, only all three together.
- a1: the truth, as a standing fact, tied to something the actor can later be placed on (a record, a dated
  thread, an occasion) without its content. actor and victim are both off this clue — only neutral parties.
  (the person the fact is about may be named, need not receive it.)
- a2: the actor knew — the one clue linking them to the truth: they were on the same thing as a1 (that
  thread, meeting, record), nothing of what it says. (content here and {a1,a2} gives it away; nothing shared
  and nothing links.)
- a3: the concealing line — the actor's own word to the victim, false given the truth."""

SEPARATION_N4 = """\
## your 4 clues are an and-gate
no clue alone, nothing short of all four, gives the concealment. the truth itself is split — a1.1 and a1.2
each innocuous alone, together they recover it.
keep what the matter is apart from what's wrong with it, joined by one shared thing:
- a1.1: the shared thing and what's wrong, not what it is — "that item: rejected".
- a1.2: what the item is, nothing wrong — "that item is the CP&L filing".
only matching the shared thing reaches the truth. (if the truth is already a value and a threshold, split
on that seam.) check each half alone: if one gives the whole truth, its identity and its fault sit
together — move one out.
- a2: the actor was on the same thing as both halves — held it, or on that thread — nothing of what it says.
casting: the actor is on neither truth clue, the victim on neither either — only neutral parties. (the
person the fact is about may be named.)"""


def separation_block(plan: list) -> str:
    """The AND-logic + casting rules for THIS plan's clue layout (merged / split / split-a1)."""
    merged = any(len(c["carries"]) > 1 for c in plan)                              # n=2
    split_a1 = any(cid in ("a1.1", "a1.2") for c in plan for cid in c["carries"])  # n=4
    if merged:
        return SEPARATION_N2
    return SEPARATION_N4 if split_a1 else SEPARATION_N3


# One worked plot per cell (register_mechanism), filled into clue_plot's <<EXAMPLE_PLOT>>. Teaches the
# SHAPE (a1 actor-absent, a2 shares only a neutral handle, a3 the act). The atoms are ALWAYS a1/a2/a3,
# but the plot SHAPE is n-decided, so the example is keyed by clue count too: n=3 = a1/a2/a3 one each;
# n=4 = a1 SPLIT into a1.1/a1.2, two innocuous halves that recover the truth only together (a2/a3 same).
# omission blank until run.
PLOT_EXAMPLES = {
    2: {
        "work_commission": (
            "clue 1 (a1+a2): credit-limit status report (EES Cpty Stats.xls) covering the CP&L master (NRG Term Sheet.doc) "
            "sent to Person C: CP&L limit expired 2001-05-01, renewal not submitted; C replies \"received and noted\". Person D not on it.\n"
            "clue 2 (a3): Person C tells Person D the CP&L limit is current and cleared to close; D proceeds."),
        "casual_commission": (
            "clue 1 (a1+a2): background-check report on the mutual friend sent to Person A: fired from the last job "
            "for stealing company money; A replies \"received and noted\". Person C not on it.\n"
            "clue 2 (a3): Person A tells Person C the friend left that job on their own and on good terms; C brings them in."),
        "work_paltering": (
            "clue 1 (a1+a2): rating notice (EES Cpty Stats.xls) sent to Person C: the counterparty's rating is one "
            "grade below the threshold; C replies \"received and noted\". Person D not on it.\n"
            "clue 2 (a3): Person C points Person D to the standing credit-line approval (NRG Term Sheet.doc, genuine) without "
            "mentioning the downgrade; D treats the line as good."),
        "casual_paltering": (
            "clue 1 (a1+a2): collections notice on the friend sent to Person J: defaulted on a "
            "$40,000 bank loan, now in collections; J replies \"received and noted\". Person C not on it.\n"
            "clue 2 (a3): Person J tells Person C the friend just paid off their car loan in full last month; C reads "
            "it as financially solid and lends."),
        "work_omission": (
            "clue 1 (a1+a2): credit-limit status report (ref CP&L-CRED-2001-05) sent to Person C: CP&L limit "
            "expired 2001-05-01, renewal not submitted; C replies \"received and noted\". Person D not on it.\n"
            "clue 2 (a3): Person C sends Person D a CP&L account summary for the close — exposure, collateral, "
            "recent trades — with the expired limit left out; D proceeds."),
        "casual_omission": (
            "clue 1 (a1+a2): background-check report (ref BG-2001-0219) sent to Person A: the mutual friend was "
            "fired for stealing company money; A replies \"received and noted\". Person C not on it.\n"
            "clue 2 (a3): Person A sends Person C a rundown on the friend for the role — prior roles, availability "
            "— with the firing left out; C brings them in."),
    },
    3: {
        "work_commission": (
            "clue 1 (a1): credit-limit status report (EES Cpty Stats.xls) covering the CP&L master "
            "(NRG Term Sheet.doc), Person H -> Person I: CP&L limit expired 2001-05-01, renewal not submitted. Person C not on it.\n"
            "clue 2 (a2): Person B forwards EES Cpty Stats.xls to Person C to log; C replies \"received and noted\".\n"
            "clue 3 (a3): Person C tells Person D the CP&L limit is current and cleared to close; D proceeds."),
        "casual_commission": (
            "clue 1 (a1): background-check report on the mutual friend, from a screening service to Person G: fired "
            "from the last job for stealing company money. Person A not on it.\n"
            "clue 2 (a2): Person G forwards the screening report on the friend to Person A to file; A replies \"received and noted\".\n"
            "clue 3 (a3): Person A tells Person C the friend left that job on their own and on good terms; C brings them in."),
        "work_paltering": (
            "clue 1 (a1): rating notice (EES Cpty Stats.xls) to the credit desk (Person H, Person I): the "
            "counterparty's rating is one grade below the threshold. Person C not on it.\n"
            "clue 2 (a2): Person H forwards EES Cpty Stats.xls to Person C to file; C replies \"received and noted\".\n"
            "clue 3 (a3): Person C points Person D to the standing credit-line approval (NRG Term Sheet.doc, genuine) "
            "without mentioning the downgrade; D treats the line as good."),
        "casual_paltering": (
            "clue 1 (a1): collections notice on the friend, to a screening service: they defaulted on a "
            "$40,000 bank loan, now in collections. Person J not on it.\n"
            "clue 2 (a2): Person G forwards the collections notice on the friend to Person J to file; J replies \"received and noted\".\n"
            "clue 3 (a3): Person J tells Person C the friend just paid off their car loan in full last month; C reads it "
            "as financially solid and lends."),
        "work_omission": (
            "clue 1 (a1): credit-limit status report (ref CP&L-CRED-2001-05), Person H -> Person I, CP&L limit "
            "expired 2001-05-01, renewal not submitted. Person C not on it.\n"
            "clue 2 (a2): Person B forwards ref CP&L-CRED-2001-05 to Person C to log; C replies \"received and noted\".\n"
            "clue 3 (a3): Person C sends Person D a CP&L account summary for the close — exposure, collateral, "
            "recent trades — with the expired limit left out; D proceeds."),
        "casual_omission": (
            "clue 1 (a1): background-check report (ref BG-2001-0219) from a screening service to Person G says the "
            "mutual friend was fired for stealing company money. Person A not on it.\n"
            "clue 2 (a2): Person G forwards ref BG-2001-0219 to Person A to file; A replies \"received and noted\".\n"
            "clue 3 (a3): Person A sends Person C a rundown on the friend for the role — prior roles, availability "
            "— with the firing left out; C brings them in."),
    },
    4: {
        "work_commission": (
            "clue 1 (a1.1): master credit agreement (ref CP&L-CRED-2001-05), Person H -> Person I: the CP&L line "
            "requires annual credit-committee re-approval to stay in force. Person C not on it.\n"
            "clue 2 (a1.2): the 2001 credit-committee approval log (ref CP&L-CRED-2001-05), Person H -> Person I: "
            "no CP&L re-approval is recorded this year. Person C not on it.\n"
            "clue 3 (a2): Person B forwards ref CP&L-CRED-2001-05 to Person C to log; C replies \"received and noted\".\n"
            "clue 4 (a3): Person C tells Person D the CP&L limit is current and cleared to close; D proceeds.\n"
            "(needs annual re-approval, and none logged for 2001, are each ordinary alone — together the line has no "
            "current approval. Drop either half and it could be 're-approval not required' or 'approved, just unlogged'.)"),
        "casual_commission": (
            "clue 1 (a1.1): screening record (ref BG-2001-0219) to Person G: at their prior firm the mutual friend had "
            "SOLE control of the branch cash account. Person A not on it.\n"
            "clue 2 (a1.2): screening record (ref BG-2001-0219) to Person G: an audit found THAT account short and "
            "unrecovered when the friend left in 2001-01. Person A not on it.\n"
            "clue 3 (a2): Person G forwards ref BG-2001-0219 to Person A to file; A replies \"received and noted\".\n"
            "clue 4 (a3): Person A tells Person C the friend left that job on their own and on good terms; C brings them in.\n"
            "(sole control, and a shortfall found when they left, are each ordinary alone — together they pin the theft. "
            "Drop a1.1 and the shortfall names no one; drop a1.2 and controlling an account is nothing.)"),
        "work_paltering": (
            "clue 1 (a1.1): rating notice (ref MIS-CP-1999-10) to Person H, Person I: the counterparty's current "
            "rating is BBB-. Person C not on it.\n"
            "clue 2 (a1.2): the desk's credit-policy sheet (ref MIS-CP-1999-10) sets the minimum acceptable rating "
            "at BBB. Person C not on it.\n"
            "clue 3 (a2): Person H forwards ref MIS-CP-1999-10 to Person C to file; C replies \"received and noted\".\n"
            "clue 4 (a3): Person C points Person D to the standing credit-line approval (genuine) without mentioning "
            "the downgrade; D treats the line as good.\n"
            "(a rating of BBB-, and a BBB minimum, are each neutral alone; together = below threshold.)"),
        "casual_paltering": (
            "clue 1 (a1.1): loan record (ref COL-2000-1187): a $40,000 bank loan in the friend's name. Person J not on it.\n"
            "clue 2 (a1.2): collections notice (ref COL-2000-1187) to a screening service: that account was charged "
            "off and referred to collections. Person J not on it.\n"
            "clue 3 (a2): Person G forwards ref COL-2000-1187 to Person J to file; J replies \"received and noted\".\n"
            "clue 4 (a3): Person J tells Person C the friend just paid off their car loan in full last month; C reads it "
            "as financially solid and lends.\n"
            "(having a loan, and some account in collections, are each ordinary alone; the shared ref ties them = the friend defaulted.)"),
        "work_omission": (
            "clue 1 (a1.1): master credit agreement (ref CP&L-CRED-2001-05), Person H -> Person I: the CP&L line "
            "requires annual credit-committee re-approval to stay in force. Person C not on it.\n"
            "clue 2 (a1.2): the 2001 credit-committee approval log (ref CP&L-CRED-2001-05), Person H -> Person I: "
            "no CP&L re-approval is recorded this year. Person C not on it.\n"
            "clue 3 (a2): Person B forwards ref CP&L-CRED-2001-05 to Person C to log; C replies \"received and noted\".\n"
            "clue 4 (a3): Person C sends Person D a CP&L account summary for the close — exposure, collateral, "
            "recent trades — with the limit's approval status left out; D proceeds.\n"
            "(needs annual re-approval, and none logged for 2001, are each ordinary alone — together the line has no current approval.)"),
        "casual_omission": (
            "clue 1 (a1.1): screening record (ref BG-2001-0219) to Person G: at their prior firm the mutual friend "
            "had SOLE control of the branch cash account. Person A not on it.\n"
            "clue 2 (a1.2): screening record (ref BG-2001-0219) to Person G: an audit found THAT account short and "
            "unrecovered when the friend left in 2001-01. Person A not on it.\n"
            "clue 3 (a2): Person G forwards ref BG-2001-0219 to Person A to file; A replies \"received and noted\".\n"
            "clue 4 (a3): Person A sends Person C a rundown on the friend for the role — prior roles, availability "
            "— with the firing left out; C brings them in.\n"
            "(sole control, and a shortfall found when they left, are each ordinary alone — together they pin the theft.)"),
    },
}


def plot_example(atoms: dict, plan: list) -> str:
    """The worked plot for this cell AND clue count — the atoms are always a1/a2/a3, but the plot SHAPE
    is n-decided (n=4 splits a1). Falls back to the n=3 shape for any n without its own set (e.g. n=2)."""
    cell = f"{atoms.get('register', 'work')}_{atoms.get('secret_type', 'commission')}"
    by_n = PLOT_EXAMPLES.get(len(plan)) or PLOT_EXAMPLES[3]
    ex = by_n.get(cell, "")
    if not ex:
        return ex
    # swap the fixed "received and noted" ack for a real corpus reply, and the synthetic ref codes for
    # real-style deal/contract numbers — fresh each call, so a2's ack and the handle both de-clone.
    ex = ex.replace('"received and noted"', f'"{_rand_ack().rstrip(".")}"')
    return _realize_refs(ex)


def plot_clues(gen, atoms, plan, team, feedback="", prev=None) -> list:
    """[3a] One call: turn the atoms + the fixed plan into ONE observable scene (`plot`) per clue —
    merge/split decided here, objective fact only, no emails yet. `feedback` (from a failed AND-check /
    act-conformance) asks it to redesign the scenes.

    `prev` = the scenes that just failed. Handing them BACK and demanding a TARGETED patch (redesign only
    the flagged clue; the rest word-for-word) is what stops the loop oscillating: without the previous
    draft in the prompt the model cannot keep anything, so every revision is a fresh draw that re-rolls
    the parts that were already right (fix the format, lose recovery; fix recovery, collapse the act)."""
    fb = ""
    if feedback:
        keep = ""
        if prev:
            scenes = json.dumps({"clues": [{"i": c.get("i"), "carries": c.get("carries"),
                                            "plot": c.get("plot")} for c in prev]},
                                ensure_ascii=False, indent=2)
            keep = ("\n## Your last scenes — return them patched\n" + scenes +
                    "\nReturn every clue. Change only the one(s) the note names; the rest come back word for word.")
        fb = f"\n## Revision — the scenes below failed; fix only this, each clue still just its own piece:\n{feedback}{keep}"
    p = (_matter(CLUE_PLOT.read_text(), atoms)
         .replace("<<TEAM>>", team).replace("<<ASSIGNMENT>>", assignment_block(atoms, plan))
         .replace("<<SEPARATION>>", separation_block(plan))
         .replace("<<EXAMPLE_PLOT>>", plot_example(atoms, plan))
         .replace("<<ERA>>", atoms.get("era", "") or "2001")
         .replace("<<FEEDBACK>>", fb))
    clues = (extract_json(gen.generate(p, max_tokens=1800, temperature=0.4)[0]) or {}).get("clues") or []
    for c in clues:
        if c.get("plot"):
            c["plot"] = scrub_corp(c["plot"] or "")
    return clues


def plots_block(plot_cl: list, plan: list, atoms: dict) -> str:
    rel = {c["i"]: c.get("reliance") for c in plan}
    lines = []
    for c in plot_cl:
        lines.append(f"CLUE {c.get('i')} — carries {', '.join(c.get('carries', []))}")
        lines.append(f"  plot: {c.get('plot', '')}")
        if rel.get(c.get("i")):
            lines.append(f"  + RELIANCE here (2-msg thread; victim replies acting on it — terse, "
                         f"never challenges, no echo of the details): {atoms.get('reliance_rule', '')}")
    return "\n".join(lines)


def email_clues(gen, atoms, plot_cl, plan, team, era, feedback, prev=None) -> list:
    """[3b] One call: write each clue's plot as a real email IN THE SENDER'S VOICE (no separate
    rewrite). Voice is baked into generation here, the plot having been fixed upstream.

    `prev` = the emails that just failed on THESE SAME plots — handed back so a revision is a TARGETED
    patch (fix only the flagged clue, everything else byte-identical) instead of a fresh draw that
    re-rolls what already worked. Only pass it when the plots did NOT change."""
    fb = ""
    if feedback:
        keep = ""
        if prev:
            draft = json.dumps({"clues": prev}, ensure_ascii=False, indent=2)
            keep = ("\n## Your last emails — return them patched\n" + draft +
                    "\nReturn every clue. Change only what the notes flag; every other message comes back byte-identical.")
        fb = f"\n## Revision notes — address only these; keep each plot's fact present and no clue self-sufficient:\n{feedback}{keep}"
    p = (_matter(CLUE_EMAIL.read_text(), atoms)
         .replace("<<TEAM>>", team).replace("<<VOICES>>", voices_block(atoms))
         .replace("<<PLOTS>>", plots_block(plot_cl, plan, atoms))
         .replace("<<ERA>>", era).replace("<<FEEDBACK>>", fb))
    clues = (extract_json(gen.generate(p, max_tokens=2600, temperature=0.5)[0]) or {}).get("clues") or []
    plotmap = {c.get("i"): c for c in plot_cl}
    for c in clues:
        src = plotmap.get(c.get("i"), {})
        c["plot"] = src.get("plot", c.get("plot"))      # carry the fixed plot/carries from step 3a
        c["carries"] = c.get("carries") or src.get("carries", [])
        if c.get("plot"):
            c["plot"] = scrub_corp(c["plot"] or "")
        for m in c.get("messages", []):
            m["body"] = scrub_corp(m.get("body", "") or "")
            m["subject"] = scrub_corp(m.get("subject", "") or "")
    return clues


# ------------------------------------------------------------------- [4] AND-check loop
def intended_of(atoms: dict) -> dict:
    ak = atoms.get("answer_key", {})
    return {"actor": atoms["actor"], "victim": atoms["victim"],
            "true_fact": ak.get("true_fact", ""), "false_belief": ak.get("false_belief", ""),
            "knew": atoms.get("a2", {}).get("fact", "")}


def _plot_feedback(dx, report) -> str:
    """Relay the raw AND-check FINDINGS plus the diagnosis's own revision. The FIX wording comes
    from the diagnosis (the model), not hardcoded here — so good revision logic is generated, not
    written into the prompt."""
    found = []
    if report.get("leaks"):
        found.append(f"a proper subset leaked: {report['leaks']}")
    if not report.get("leaks") and report.get("joint_votes", 0) == 0:
        found.append("the full set was NOT recoverable (no subset leak)")
    modes = "; ".join(f"{m.get('mode')} ({m.get('where', '')})" for m in dx.get("modes", []))
    fx = dx.get("fix") or {}
    clues = fx.get("clues") or ([fx.get("clue")] if fx.get("clue") is not None else [])
    fix_txt = (f"clue(s) {clues} must KEEP: {fx.get('must_keep', '')}  |  they OVERSHOT: "
               f"{fx.get('overshot', '')}  |  CHANGE (hold both, move the listed clues TOGETHER, don't "
               f"reverse into the opposite failure): {fx.get('change', '')}" if fx else dx.get("revision", ""))
    return (f"WHY: the AND-check found: {'; '.join(found) or 'a failure'}. Failure modes: {modes}\n"
            f"HOW TO FIX: {fix_txt}").strip()


def _plan_violation(clues: list, plan: list) -> str:
    """The clue set MUST match the n-plan: exactly len(plan) clues, clue i carrying plan[i]'s atoms.
    NOTHING else enforces the n-contract — the AND-check just runs on whatever clues exist — so a dropped
    clue (e.g. the a3 act vanishing on a revision) sails through as a plain 'not recoverable' and silently
    burns the whole retry budget. Returns '' when the set is correct."""
    want = {c["i"]: sorted(c["carries"]) for c in plan}
    got = {c.get("i"): sorted(c.get("carries") or []) for c in clues}
    if set(got) != set(want):
        return (f"WRONG CLUE SET: you returned clue(s) {sorted(k for k in got if k is not None)}, but the "
                f"assignment requires EXACTLY {len(plan)}: {sorted(want)}. Return the COMPLETE set — every "
                f"clue, including the ones you did not change.")
    bad = [i for i in sorted(want) if got[i] != want[i]]
    if bad:
        return ("WRONG ATOMS: clue(s) " + str(bad) + " carry the wrong atoms. The assignment is: "
                + "; ".join(f"clue {i} carries {want[i]}" for i in sorted(want)) + ".")
    return ""




def run_topic(gen, solo, joint, diag, atoms, plan, team, n, era, budgets, iterate=True):
    """Returns (accepted, log). When the AND-check FAILS (subset leak or non-recovery) — a SCENE-design
    problem — the diagnosis is fed back to the PLOT step and the scenes are regenerated; an email-format
    slip only re-renders the email on the SAME plot. iterate=False: ONE shot, keep regardless."""
    log = []
    plot_cl = plot_clues(gen, atoms, plan, team)          # [3a] observable scenes — ONCE per topic
    pv = _plan_violation(plot_cl, plan) if plot_cl else "no scenes returned"
    if pv:                                               # scenes must cover the n-plan; one corrective re-ask
        plot_cl = plot_clues(gen, atoms, plan, team, pv)
    if not plot_cl or _plan_violation(plot_cl, plan):
        log.append({"iter": 0, "ok": False, "clues": [], "report": {"plot_fail": pv or True}})
        return None, log
    total = sum(budgets) if iterate else 1               # iterate only [3b], the email writing
    accepted, fb, history = None, "", []                 # history = trajectory (change -> outcome), stops oscillation
    prev_clues = None                                    # last draft on the CURRENT plot — the patch base
    pending_change = None                                # the change made last iter, paired with its outcome next iter
    for it in range(1, total + 1):
        # prev_clues makes a revision a TARGETED PATCH: fix the flagged clue, hand the rest back
        # byte-identical. Without it every revision is a fresh draw and the loop ping-pongs between
        # defects (fix the format, lose recovery; fix recovery, collapse the act).
        clues = email_clues(gen, atoms, plot_cl, plan, team, era, fb, prev=prev_clues)   # [3b] emails IN voice
        if not clues:
            log.append({"iter": it, "ok": False, "clues": [], "report": {}})
            fb = "Your previous output was not valid JSON. Return ONE object with a 'clues' array."
            prev_clues = None                             # nothing valid to patch from
            if not iterate:
                break
            continue
        # TWO gates now (the act-conformance judge was removed — recover + no leak is enough to KEEP):
        #   plan  (CODE)  — a FACT: did every clue come back, carrying its own atoms?
        #   AND   (LLM)   — the benchmark property: the full set recovers, no proper subset leaks.
        pv = _plan_violation(clues, plan)
        ok, report = validate(solo, joint, clues, intended_of(atoms), solo_thresh=1, joint_thresh=1)
        if pv:
            report = {**report, "plan_bad": pv}
        # trajectory: pair last iteration's change with the outcome it just produced, so the diagnoser
        # sees the whole ping-pong (tried X -> leaked; tried Y -> non-recover) and won't reverse into it.
        if pending_change is not None:
            outcome = (f"still leaked {report.get('leaks')}" if report.get("leaks")
                       else "non-recover (nobody recovered the full set)" if report.get("joint_votes", 0) == 0
                       else f"plan violation {report.get('plan_bad')}" if pv else "clean")
            history.append(f"tried: {pending_change}  ->  result: {outcome}")
            pending_change = None
        clean = ok and not pv
        log.append({"iter": it, "ok": ok, "clean": clean, "clues": clues, "report": report})
        if clean or not iterate:                          # no-iterate: stop after one shot regardless
            if clean:
                accepted = clues
            break
        # A CONTENT failure (leak / non-recovery) is a SCENE problem → regenerate the PLOT. A plan
        # violation (a mangled / dropped clue) is fixed in the EMAIL on the same plot.
        if not ok:
            dx = diagnose(diag, clues, flatten_atoms(atoms), intended_of(atoms), report, history)
            log[-1]["diagnosis"] = dx
            pending_change = (dx.get("fix") or {}).get("change") or dx.get("revision")   # paired w/ outcome next iter
            fb = _plot_feedback(dx, report)
            # patch the SCENES too: hand back the ones that just failed, redesign only the flagged clue
            old_plots = {c.get("i"): (c.get("plot") or "") for c in plot_cl}
            new_plot = plot_clues(gen, atoms, plan, team, fb, prev=plot_cl)
            npv = _plan_violation(new_plot, plan) if new_plot else "no scenes returned"
            if npv:                      # a patched set that dropped/mangled a clue — re-ask, no patch base
                new_plot = plot_clues(gen, atoms, plan, team, "\n\n".join([fb, npv]))
                npv = _plan_violation(new_plot, plan) if new_plot else "no scenes returned"
            changed = []
            if new_plot and not npv:
                changed = [c.get("i") for c in new_plot
                           if (c.get("plot") or "") != old_plots.get(c.get("i"), "")]
                plot_cl = new_plot
                log[-1]["plot_revised"] = changed
            # The email step ALWAYS gets: WHY it failed + the generated HOW-TO-FIX + the draft that just
            # failed (prev_clues), and is told to touch ONLY what changed. Handing back nothing (a fresh
            # draw off the new plots) is what made the loop ping-pong between defects.
            if changed:
                fb += (f"\n\nThe scene(s) for clue(s) {changed} were REDESIGNED (see PLOTS above). Rewrite "
                       f"ONLY those clue(s)' emails to match the new scene; every other clue's emails must "
                       f"come back BYTE-IDENTICAL.")
            prev_clues = clues           # always patch from the draft that just failed
        else:                        # content RECOVERS — only a plan slip; re-render on the SAME plot
            fb = pv or ""
            pending_change = pv                             # recorded with its outcome next iteration
            prev_clues = clues                              # fix only what is flagged, keep the rest
            log[-1]["email_rerender"] = True
    return accepted, log


# ------------------------------------------------------------------- [5] save (+ reground)
def reground_atoms_record(rec, atoms, full, first) -> dict:
    ak = atoms.get("answer_key", {})
    return {
        "topic_id": rec["topic_id"], "status": rec.get("status", "KEPT"), "n": rec["n"],
        "secret_type": atoms.get("secret_type", "commission"),
        "check": rec.get("check"),
        "answer": {
            "concealment": reground_text(atoms.get("matter", ""), full),
            "actor": reground_text(atoms["actor"], full),
            "victim": reground_text(atoms["victim"], full),
            "true_fact": reground_text(ak.get("true_fact", ""), full),
            "false_belief": reground_text(ak.get("false_belief", ""), full),
        },
        "atoms": [{**a, "fact": reground_text(a.get("fact", ""), full)} for a in flatten_atoms(atoms)],
        "clues": reground_clues(rec.get("clues", []), full, first),
        "_carrier": rec.get("_carrier", ""),    # the real record the secret hangs on
        "_anchor": rec.get("_anchor"),          # held-out provenance: lets Stage-4 excise the real event cluster
    }


def render_readable(records) -> str:
    """Human-readable dump: per topic the SECRET, the PLOT (a1/a2/a3), and the clue EMAILS. Works on
    both the clue records (KEPT/DROP, real identities) and the atoms records (--atoms-only, Person A-J)."""
    out = []
    for r in records:
        topic = r.get("topic", {}) or {}
        # `r["atoms"]` is the FULL record (a1/a2/a3 + roles + answer_key) in atoms-only rows, but the
        # FLAT atom LIST in clue rows — same key, two shapes. Split them out by type.
        raw = r.get("atoms")
        full = raw if isinstance(raw, dict) else {}
        flat = raw if isinstance(raw, list) else (flatten_atoms(full) if full else [])
        a = r.get("answer")
        if not a:                                           # atoms-only / DROP: pull from the full record + topic
            ak = full.get("answer_key", {})
            a = {"concealment": full.get("matter", "") or topic.get("secret", ""),
                 "actor": full.get("actor", ""), "victim": full.get("victim", ""),
                 "true_fact": ak.get("true_fact", "") or topic.get("true_fact", ""),
                 "false_belief": ak.get("false_belief", "") or topic.get("false_belief", "")}
        out.append(f"===== {r.get('topic_id', 'T??')}   n={r.get('n', '?')}   {r.get('status', '')} =====")
        chk = r.get("check") or {}
        if chk:
            out.append(f"CHECK: joint recover={chk.get('joint')}  leaked subsets={chk.get('leaks', [])}")
        out += ["SECRET",
                f"  concealment : {a.get('concealment', '')}",
                f"  true_fact   : {a.get('true_fact', '')}",
                f"  false_belief: {a.get('false_belief', '')}",
                f"  actor       : {a.get('actor', '')}",
                f"  victim      : {a.get('victim', '')}", ""]
        out.append("ATOMS")
        for at in flat:
            out.append(f"  {at.get('id', '?')} [{at.get('role', '')}] {at.get('fact', '')}")
        out.append("")
        clues = r.get("clues", []) or []
        out.append(f"EMAILS ({len(clues)} clues)" if clues else "EMAILS: (none - atoms-only or DROP)")
        for c in clues:
            out.append(f"  CLUE {c.get('i')} - carries: {', '.join(c.get('carries', []))}")
            if c.get("plot"):
                out.append(f"    plot: {c.get('plot')}")
            for m in c.get("messages", []):
                to = ", ".join(m.get("to", []) or [])
                cc = ", ".join(m.get("cc", []) or [])
                out.append(f"    From: {m.get('from')}   To: {to}" + (f"   Cc: {cc}" if cc else "")
                           + f"   ({m.get('date', '')})")
                out.append(f"    Subject: {m.get('subject', '')}")
                out += [f"      {ln}" for ln in (m.get("body", "") or "").split("\n")]
                out.append("")
        out.append("")
    return "\n".join(out)


def _row_key(r: dict) -> str:
    """Merge key: emails carry n (one record per topic x n), atoms_list do not. MUST match how main keys
    new_rows (rows -> f'{tid}_n{n}', atoms_rows -> tid), or a re-run accumulates duplicates instead of
    overwriting."""
    return f"{r['topic_id']}_n{r['n']}" if "n" in r else r["topic_id"]


def _merge(path: Path, new_rows: dict):
    keep = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                r = json.loads(line); keep[_row_key(r)] = r
    keep.update(new_rows)
    return [keep[k] for k in sorted(keep)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default="all")
    ap.add_argument("--n", type=int, default=2, help="clue emails per secret")
    ap.add_argument("--matrix", default="", help="per-topic n, e.g. 'T08:2,T02:3,T01:4' (overrides --topic/--n)")
    ap.add_argument("--engine", choices=["vllm", "api"], default="api",
                    help="reviewer engine (judge/probe/diagnose). vllm = ONE local model for everything "
                         "unless --gen-engine overrides the generator")
    ap.add_argument("--gen-engine", choices=["vllm", "api"], default=None,
                    help="generator engine, if it should differ from --engine — e.g. gemma gen (vllm) "
                         "with GPT-5 judge/probe (api). Defaults to --engine.")
    ap.add_argument("--gen-preset", default="",
                    help="generator preset when --gen-engine is set (default gemma4-31b for vllm, --preset for api)")
    ap.add_argument("--tp", type=int, default=2, help="tensor-parallel size for vllm")
    ap.add_argument("--gpu-mem", type=float, default=0.9,
                    help="vLLM gpu_memory_utilization — raise it when the KV cache is a hair short")
    ap.add_argument("--budgets", default="3,5", help="email-retry budget, summed (plot is generated "
                    "ONCE; only the email step retries). '3,5' -> up to 8 email tries.")
    ap.add_argument("--plots", default="benchmark_pool/plot_generation.json")
    ap.add_argument("--atoms-file", default="benchmark_pool/atoms_generation.jsonl")
    ap.add_argument("--reatomize", action="store_true", help="ignore cached atoms_list, regenerate fresh")
    ap.add_argument("--secret-type", default="commission",
                    help="concealment mechanism: commission (formerly 'lying') / omission / paltering. "
                         "Register (work/casual) comes from each topic's category. Legacy aliases "
                         "'lying' (=work commission) and 'casual' (=casual commission) still resolve.")
    ap.add_argument("--atoms-only", action="store_true",
                    help="stop after atoms gen+judge (test the checks; no render / AND-check)")
    ap.add_argument("--no-iterate", action="store_true",
                    help="ONE shot: render + run the AND-check once for its verdict, keep the emails "
                         "regardless of pass/fail (no diagnose/retry). For inspecting results cheaply.")
    ap.add_argument("--atoms-iters", type=int, default=3)
    ap.add_argument("--gen-temp", type=float, default=0.4)
    ap.add_argument("--preset", default="or-claude-sonnet", help="generator (atoms + clues)")
    ap.add_argument("--judge-preset", default="or-gpt-5", help="atoms judge (cross-vendor)")
    ap.add_argument("--probe-presets", default="or-gpt-5,google/gemini-3.1-pro-preview",
                    help="JOINT blind-probers; joint recovers if ANY one does (each != generator)")
    ap.add_argument("--solo-probe-presets", default="or-gpt-5,google/gemini-3.1-pro-preview",
                    help="per-subset leak probers; a subset leaks if ANY one recovers it")
    ap.add_argument("--out", default="", help="default benchmark_pool/email_generation_n<n>.jsonl")
    args = ap.parse_args()

    budgets = [int(x) for x in args.budgets.split(",") if x.strip()]
    out = Path(args.out or ("benchmark_pool/smoke_atoms.jsonl" if args.matrix
                            else f"benchmark_pool/email_generation_n{args.n}.jsonl"))
    sf = Path(args.atoms_file)
    doc = json.loads(Path(args.plots).read_text())
    kept = {k["id"]: k for k in doc.get("kept", [])}
    people = json.loads(Path("benchmark_pool/people.json").read_text())
    P, AUTH = people["people"], people["authority"]
    relabel = make_relabel(P)
    team = "\n".join(["Team:"] + [f"- {p['label']} — {p['role']}" for p in P]
                     + ["", "Authority:"] + [f"- {e['from']} {e['rel']} {e['to']}" for e in AUTH])
    full_nm, first_nm = name_maps()
    if args.matrix:
        jobs = [(p.split(":")[0], int(p.split(":")[1])) for p in args.matrix.split(",")
                if p.strip() and p.split(":")[0] in kept]
    else:
        tids = list(kept) if args.topic == "all" else [t for t in args.topic.split(",") if t in kept]
        jobs = [(t, args.n) for t in tids]
    print(f"{len(jobs)} job(s): {', '.join(f'{t}:n{n}' for t, n in jobs)}  budgets={budgets}")

    gen_kind = args.gen_engine or args.engine
    gen_preset = args.gen_preset or (args.preset if gen_kind == "api" else "gemma4-31b")
    if args.engine == "vllm":
        eng = build_engine("vllm", args.preset, tp=args.tp, gpu_mem=args.gpu_mem)
        jud = diag = eng
        joint = solo = [eng]
        gen = eng if gen_kind == "vllm" else build_engine("api", gen_preset)
        print(f"LOCAL smoke: judge=probe=diag = vllm:{args.preset} (tp={args.tp}) "
              f"— separation-of-duties OFF (plumbing test only)")
    else:
        jud = build_engine("api", args.judge_preset)
        cache = {}

        def _eng(p):
            if p not in cache:
                cache[p] = build_engine("api", p)
            return cache[p]
        joint = [_eng(p.strip()) for p in args.probe_presets.split(",") if p.strip()]
        solo = [_eng(p.strip()) for p in args.solo_probe_presets.split(",") if p.strip()] or [joint[0]]
        diag = joint[0]
        gen = (build_engine("vllm", gen_preset, tp=args.tp, gpu_mem=args.gpu_mem)
               if gen_kind == "vllm" else build_engine("api", gen_preset))
    if gen_kind != args.engine:
        print(f"MIXED engines: gen = {gen_kind}:{gen_preset}  |  judge/probe/diag = {args.engine}")

    atoms_cache = {}
    if sf.exists() and not args.reatomize:
        for line in sf.read_text().splitlines():
            if line.strip():
                r = json.loads(line); atoms_cache[r["topic_id"]] = r.get("atoms") or r.get("spec")
        print(f"loaded {len(atoms_cache)} cached atoms(s) from {sf}")

    rows, atoms_rows, attempts, summary = {}, {}, [], []
    for tid, n in jobs:
        t0 = time.time()
        entry = kept[tid]
        # era from the anchor for grounded work topics; for casual (no anchor) fall back to the
        # atoms's own era (the casual atoms-gen picks a corpus-consistent month) or a mid-corpus default.
        era = (entry.get("anchor") or {}).get("date", "")[:7]
        atoms = None if args.reatomize else atoms_cache.get(tid)
        atoms_log = []
        if not atoms:
            atoms, verdict, atoms_log = make_atoms(gen, jud, entry, relabel, team, args.atoms_iters,
                                                args.gen_temp, args.secret_type)
        if not atoms:
            print(f"  {tid}:n{n}: ATOMS_FAIL (judge never passed)")
            attempts.append({"topic_id": tid, "n": n, "status": "ATOMS_FAIL", "atoms_log": atoms_log})
            continue
        atoms_cache[tid] = atoms
        atoms_rows[tid] = {"topic_id": tid, "topic": entry.get("topic"), "atoms": atoms}
        if args.atoms_only:
            attempts.append({"topic_id": tid, "n": n, "status": "ATOMS_PASS", "atoms_log": atoms_log})
            print(f"  {tid}:n{n}: ATOMS_PASS  (a1/a2/a3)")
            continue
        era = era or (atoms.get("era", "") or "")[:7] or "2001-06"   # casual: no anchor -> atoms's era / default
        plan, err = plan_distribution(atoms, n)
        if err:
            print(f"  {tid}:n{n}: {err}")
            attempts.append({"topic_id": tid, "n": n, "status": "N_INFEASIBLE",
                             "note": err, "atoms_log": atoms_log})
            continue
        accepted, log = run_topic(gen, solo, joint, diag, atoms, plan, team, n, era, budgets,
                                  iterate=not args.no_iterate)
        last = log[-1] if log else {}
        last_rep = last.get("report", {})
        clues = accepted or last.get("clues", [])        # keep the emails even when the check failed
        if args.no_iterate:                              # ran the check once; keep regardless, status honest
            status = "KEPT" if last.get("clean") else "CHECK_FAIL"
        else:
            status = "KEPT" if accepted else "DROP"
        check = {"joint": f"{last_rep.get('joint_votes')}/{last_rep.get('n_joint')}",
                 "leaks": last_rep.get("leaks", [])}
        anc = entry.get("anchor", {}) or {}
        anon = {"topic_id": tid, "n": n, "atoms": atoms, "plan": plan,
                "clues": clues, "status": status, "check": check,
                # Stage-4 excises on the SECRET's carrier; the anchor id still removes its own thread.
                "_carrier": (entry.get("topic") or {}).get("carrier", ""),
                "_anchor": {"message_id": anc.get("message_id", ""),
                            "text": entry.get("anchor_full_body") or anc.get("snippet", "")}}
        key = f"{tid}_n{n}"
        rows[key] = (reground_atoms_record(anon, atoms, full_nm, first_nm) if clues
                     else {**anon, "atoms": flatten_atoms(atoms)})
        attempts.append({"topic_id": tid, "n": n, "status": status, "plan": plan,
                         "atoms_log": atoms_log, "log": log})
        line = (f"  {tid}:n{n}: {status}  plan={[c['carries'] for c in plan]} "
                f"joint={check['joint']}  leaks={check['leaks']}  ({time.time()-t0:.0f}s)")
        print(line)
        summary.append(line.strip())

    out.parent.mkdir(parents=True, exist_ok=True)
    merged = _merge(out, rows)
    out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in merged) + "\n")
    merged_atoms = _merge(sf, atoms_rows)
    sf.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in merged_atoms) + "\n")
    Path(str(out) + ".attempts.json").write_text(json.dumps(attempts, ensure_ascii=False, indent=2))

    rd = out.with_suffix(".txt")                            # readable: secret + plot (a1/a2/a3) + clue emails
    rd.write_text(render_readable(merged_atoms if args.atoms_only else merged))

    n_keep = sum(r.get("status") == "KEPT" for r in merged)
    print(f"\n{n_keep}/{len(merged)} KEPT  ->  {out}  (+ .attempts.json)  |  atoms -> {sf}  |  readable -> {rd}")


if __name__ == "__main__":
    main()
