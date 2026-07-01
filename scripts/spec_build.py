#!/usr/bin/env python3
"""Spec-driven email generation — the upgraded architecture (lying).

  [1] topic + anchor  -> ATOMS: three clean facts a1 (truth F) / a2 (actor knows F) / a3 (false line)
        -> atom judge (faithful + clean a1/a2/a3 + decomposable); iterate     (prompts/spec_*_lying.md)
  [2] plan_distribution(spec, n): fixed n=2/3/4 template -> which atom(s) each clue carries
  [3a] atoms + plan -> ONE observable PLOT per clue (merge/split)             (prompts/clue_plot.md)
  [3b] plots + voice -> clue emails written in each sender's own hand         (prompts/clue_email.md)
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

  uv run python scripts/spec_build.py --topic T02 --n 3
  uv run python scripts/spec_build.py --topic all --n 2 --budgets 3,5
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, "scripts")
sys.path.insert(0, ".")
from plot_assemble import make_relabel, scrub_corp                                   # noqa: E402
from email_generate import (extract_json, render, build_team, validate, diagnose)    # noqa: E402
from email_build import (chain_violations, placeholder_violations, letter_violations)  # noqa: E402
from reground import name_maps, reground_clues, reground_text, FIRM                   # noqa: E402
from src.models.engine_factory import build_engine                                   # noqa: E402

CLUE_PLOT = Path("prompts/clue_plot.md")      # [3a] atoms+plan -> observable scene (plot) per clue
CLUE_EMAIL = Path("prompts/clue_email.md")    # [3b] plots+voice -> real emails in each sender's hand
STYLE_BANK = Path("benchmark_pool/style_bank.json")
_BANK = None


def spec_paths(secret_type: str):
    """Type-specific prompts. Add a new secret_type by dropping in two files —
    spec_generate_<type>.md (the atom model) and spec_judge_<type>.md (that type's checks);
    no code change needed (the judge's check set is read dynamically)."""
    return (Path(f"prompts/spec_generate_{secret_type}.md"),
            Path(f"prompts/spec_judge_{secret_type}.md"))


def _checks(v: dict) -> list:
    """All check entries (a dict carrying a 'verdict') in a judge verdict — type-agnostic, so each
    secret_type's judge may declare its own check set."""
    return [(k, val) for k, val in (v or {}).items()
            if isinstance(val, dict) and "verdict" in val]


def _anchor_block(entry: dict, relabel) -> str:
    a = entry["anchor"]
    body = entry.get("anchor_full_body") or a.get("snippet", "")
    to = ", ".join(relabel(x) for x in a.get("to", [])) or "(internal)"
    return (f'From: {relabel(a["from"])}  ->  To: {to}   ({(a.get("date", "") or "")[:10]})\n'
            f'Subject: "{relabel(a.get("subject", ""))}"\n\n{relabel(body)}')


def _pass(v) -> bool:
    chk = _checks(v)
    return bool(chk) and all(val.get("verdict", "").upper() == "PASS" for _, val in chk)


def _feedback_checks(v, what) -> str:
    lines = [f"- {k} [{val.get('verdict')}]: {val.get('reason', '')}"
             for k, val in _checks(v) if val.get("verdict", "").upper() != "PASS"]
    return (f"Prior {what} failed review:\n" + "\n".join(lines)
            + (f"\nFIX: {v.get('fix', '')}" if v.get("fix") else "")
            + f"\nReturn ONE corrected {what} JSON, nothing else.")


# ------------------------------------------------------------------- [1] spec generate + judge
# Topics come from STAGE 1 secret-first grounding (scripts/ground_topics.py --secret-type lying →
# topics_lying.json); this runner reads them via --plots and decomposes each into a SPEC.
def build_spec_prompt(entry: dict, relabel, team: str, gen_path: Path) -> str:
    t = entry["topic"]
    topic_json = json.dumps({"id": entry["id"], "name": t.get("name", ""),
                             "secret": t.get("secret", ""), "true_fact": t.get("true_fact", ""),
                             "false_belief": t.get("false_belief", "")},
                            indent=2, ensure_ascii=False)
    return scrub_corp(gen_path.read_text()
                      .replace("<<TOPIC>>", topic_json).replace("<<ANCHOR>>", _anchor_block(entry, relabel))
                      .replace("<<RELATIONSHIPS>>", team).replace("<<TID>>", entry["id"]))


def _spec_context(prompt: str) -> str:
    i, j = prompt.find("## SECRET"), prompt.find("## The model of")
    return prompt[i:j].strip() if (i != -1 and j != -1) else prompt


def judge_spec(jud, ctx: str, spec: dict, judge_path: Path) -> dict | None:
    p = (judge_path.read_text().replace("<<CONTEXT>>", ctx)
         .replace("<<CANDIDATE>>", json.dumps(spec, indent=2, ensure_ascii=False)))
    return extract_json(jud.generate(p, max_tokens=1600, temperature=0.0)[0])


def make_spec(gen, jud, entry, relabel, team, max_iters, temp, secret_type="lying"):
    """Generate -> judge -> feedback loop, using the secret_type's prompts. Returns (spec|None, verdict|None, log)."""
    gen_path, judge_path = spec_paths(secret_type)
    base = build_spec_prompt(entry, relabel, team, gen_path)
    ctx = _spec_context(base)
    prompt, log = base, []
    for it in range(1, max_iters + 1):
        cand = extract_json(gen.generate(prompt, max_tokens=2600, temperature=temp)[0])
        if not cand or not cand.get("a1") or not cand.get("a3"):
            log.append({"iter": it, "result": "parse_fail"})
            prompt = base + "\n\n## CORRECTION\nReturn ONLY the SPEC JSON object, with a1/a2/a3."
            continue
        v = judge_spec(jud, ctx, cand, judge_path)
        ok = _pass(v)
        log.append({"iter": it, "result": "PASS" if ok else "fail",
                    "verdicts": {k: val.get("verdict") for k, val in _checks(v)} if v else None})
        if ok:
            return cand, v, log
        prompt = base if v is None else base + "\n\n## CORRECTION REQUIRED\n" + _feedback_checks(v, "SPEC")
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


def plan_distribution(spec: dict, n: int):
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


def _atom_index(spec: dict) -> dict:
    return {
        "a1": {"role": "true_state", "fact": spec["a1"].get("fact", "")},
        "a2": {"role": "knew", "fact": spec["a2"].get("fact", "")},
        "a3": {"role": "false_statement", "fact": spec["a3"].get("fact", "")},
    }


def assignment_block(spec: dict, plan: list) -> str:
    idx, lines = _atom_index(spec), []
    split = any(cid in ("a1.1", "a1.2") for c in plan for cid in c["carries"])
    for c in plan:
        merge = " (MERGE into ONE observation)" if len(c["carries"]) > 1 else ""
        lines.append(f"CLUE {c['i']} — carries: {', '.join(c['carries'])}{merge}")
        for cid in c["carries"]:
            if cid in ("a1.1", "a1.2"):
                half = "FIRST" if cid == "a1.1" else "SECOND"
                lines.append(f"    {cid} = the {half} half of a1 (split a1; see a1 below)")
            else:
                a = idx.get(cid, {})
                lines.append(f"    {cid} [{a.get('role', '')}] {a.get('fact', '')}")
        if c.get("reliance"):
            lines.append(f"    + RELIANCE here (2-msg thread, victim replies acting on it): "
                         f"{spec.get('reliance_rule', '')}")
    if split:
        lines.append(f"\na1 (the FULL truth, to split across a1.1 and a1.2): {idx['a1']['fact']}")
        lines.append("  Split a1 into TWO observations — a1.1 and a1.2 — each INNOCUOUS on its own "
                     "(neither reveals the truth alone); read together they recover a1.")
    return "\n".join(lines)


def flatten_atoms(spec: dict) -> list:
    """Flat list for storage / regrounding: the three atoms a1, a2, a3."""
    idx = _atom_index(spec)
    return [{"id": k, **idx[k]} for k in ("a1", "a2", "a3")]


# ------------------------------------------------------------------- [3] render clues (one call)
def voices_block(spec: dict) -> str:
    global _BANK
    if _BANK is None:
        _BANK = json.loads(STYLE_BANK.read_text()) if STYLE_BANK.exists() else {}
    text = " ".join(str(spec.get(k, "")) for k in ("actor", "victim", "casting_note"))
    text += " " + " ".join(spec.get(k, {}).get("fact", "") for k in ("a1", "a2", "a3"))
    labels = set(re.findall(r"Person [A-J]", text))
    use = [l for l in _BANK if l in labels] or list(_BANK)
    return "\n\n".join(f"{lab} — {(_BANK[lab].get('card') or '').strip()}" for lab in use) \
        or "(no voice samples available)"


def _matter(p: str, spec: dict) -> str:
    return (p.replace("<<ACTOR>>", spec["actor"]).replace("<<VICTIM>>", spec["victim"])
            .replace("<<COUNTERPARTY>>", spec.get("counterparty", "the counterparty"))
            .replace("<<MATTER>>", spec.get("matter", "")))


def plot_clues(gen, spec, plan, team, feedback="") -> list:
    """[3a] One call: turn the atoms + the fixed plan into ONE observable scene (`plot`) per clue —
    merge/split decided here, objective fact only, no emails yet. `feedback` (from a failed AND-check)
    asks it to redesign the scenes."""
    fb = (f"\n## REVISION — the previous scenes failed the AND-check; redesign them to fix this, each "
          f"clue still only its own piece:\n{feedback}\n" if feedback else "")
    p = (_matter(CLUE_PLOT.read_text(), spec)
         .replace("<<TEAM>>", team).replace("<<ASSIGNMENT>>", assignment_block(spec, plan))
         .replace("<<FEEDBACK>>", fb))
    clues = (extract_json(gen.generate(p, max_tokens=1800, temperature=0.4)[0]) or {}).get("clues") or []
    for c in clues:
        if c.get("plot"):
            c["plot"] = scrub_corp(c["plot"] or "")
    return clues


def plots_block(plot_cl: list, plan: list, spec: dict) -> str:
    rel = {c["i"]: c.get("reliance") for c in plan}
    lines = []
    for c in plot_cl:
        lines.append(f"CLUE {c.get('i')} — carries {', '.join(c.get('carries', []))}")
        lines.append(f"  plot: {c.get('plot', '')}")
        if rel.get(c.get("i")):
            lines.append(f"  + RELIANCE here (2-msg thread; victim replies acting on it — terse, "
                         f"never challenges, no echo of the details): {spec.get('reliance_rule', '')}")
    return "\n".join(lines)


def email_clues(gen, spec, plot_cl, plan, team, era, feedback) -> list:
    """[3b] One call: write each clue's plot as a real email IN THE SENDER'S VOICE (no separate
    rewrite). Voice is baked into generation here, the plot having been fixed upstream."""
    fb = (f"\n## REVISION NOTES — address these; keep every plot's fact present and no clue "
          f"self-sufficient:\n{feedback}\n" if feedback else "")
    p = (_matter(CLUE_EMAIL.read_text(), spec)
         .replace("<<TEAM>>", team).replace("<<VOICES>>", voices_block(spec))
         .replace("<<PLOTS>>", plots_block(plot_cl, plan, spec))
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
def intended_of(spec: dict) -> dict:
    ak = spec.get("answer_key", {})
    return {"actor": spec["actor"], "victim": spec["victim"],
            "true_fact": ak.get("true_fact", ""), "false_belief": ak.get("false_belief", "")}


def _plot_feedback(dx, report) -> str:
    """Relay the raw AND/structure FINDINGS plus the diagnosis's own revision. The FIX wording comes
    from the diagnosis (the model), not hardcoded here — so good revision logic is generated, not
    written into the prompt."""
    found = []
    if report.get("leaks"):
        found.append(f"a proper subset leaked: {report['leaks']}")
    if report.get("chain_bad"):
        found.append(f"not one clean thread: clue(s) {report['chain_bad']}")
    if not report.get("leaks") and report.get("joint_votes", 0) == 0:
        found.append("the full set was NOT recoverable (no subset leak)")
    modes = "; ".join(f"{m.get('mode')} ({m.get('where', '')})" for m in dx.get("modes", []))
    return (f"AND-check found: {'; '.join(found) or 'a failure'}.\nFailure modes: {modes}\n"
            f"Revision: {dx.get('revision', '')}").strip()


def _structural(clues):
    ch, ph, lv = chain_violations(clues), placeholder_violations(clues), letter_violations(clues)
    if not (ch or ph or lv):
        return None
    bad, notes = sorted(set(ch) | set(ph) | set(lv)), []
    if ch:
        notes.append("not one clean email thread — a clue is ONE thread of <= 2 emails on the same "
                     "subject, each message one sender (no '---' or '[X reply]' embedded turn)")
    if ph:
        notes.append("contains a bracketed placeholder — only '[firm]' is allowed; write the "
                     "counterparty as a natural phrase / its real name")
    if lv:
        notes.append("uses a bare single letter for a person; name everyone 'Person A'…'Person J'")
    return bad, f"Clue(s) {bad} are invalid: " + "; ".join(notes) + ". Rewrite them clean."


def run_topic(gen, solo, joint, diag, spec, plan, team, n, era, budgets, iterate=True):
    """Returns (accepted, log). When the AND-check FAILS (subset leak or non-recovery) — a SCENE-design
    problem — the diagnosis is fed back to the PLOT step and the scenes are regenerated; an email-format
    slip only re-renders the email on the SAME plot. iterate=False: ONE shot, keep regardless."""
    log = []
    plot_cl = plot_clues(gen, spec, plan, team)          # [3a] observable scenes — ONCE per topic
    if not plot_cl:
        log.append({"iter": 0, "ok": False, "clues": [], "report": {"plot_fail": True}})
        return None, log
    total = sum(budgets) if iterate else 1               # iterate only [3b], the email writing
    accepted, fb, history = None, "", []                 # history = revisions tried, fed back to stop oscillation
    for it in range(1, total + 1):
        clues = email_clues(gen, spec, plot_cl, plan, team, era, fb)   # [3b] emails IN voice
        if not clues:
            log.append({"iter": it, "ok": False, "clues": [], "report": {}})
            fb = "Your previous output was not valid JSON. Return ONE object with a 'clues' array."
            if not iterate:
                break
            continue
        st = _structural(clues)
        # ALWAYS run the AND-check, even on a structural slip — a forwarded/embedded turn is usually a
        # CONTENT problem (a clue carrying another's content) the prober surfaces as a leak. ANY-recovers:
        # joint OK if >=1 prober recovers; a subset leaks if >=1 prober recovers it.
        ok, report = validate(solo, joint, clues, intended_of(spec), solo_thresh=1, joint_thresh=1)
        if st:
            report = {**report, "chain_bad": st[0]}
        clean = ok and not st                            # KEEP only if recoverable AND well-formed
        log.append({"iter": it, "ok": ok, "clean": clean, "clues": clues, "report": report})
        if clean or not iterate:                          # no-iterate: stop after one shot regardless
            if clean:
                accepted = clues
            break
        if ok:                                            # content RECOVERS and no subset leaks — only the
            fb = st[1]                                    # email's STRUCTURE slipped; re-render the email on
            log[-1]["email_rerender"] = True              # the SAME plot, keep the good scenes (don't regen plot)
            continue
        # CONTENT failed (leak or non-recovery) → diagnose, regenerate the PLOT with that feedback,
        # then re-render the email fresh from the new scenes.
        dx = diagnose(diag, clues, flatten_atoms(spec), intended_of(spec), report, history)
        log[-1]["diagnosis"] = dx
        if dx.get("revision"):
            history.append(dx["revision"])
        new_plot = plot_clues(gen, spec, plan, team, _plot_feedback(dx, report))
        if new_plot:
            plot_cl = new_plot
            log[-1]["plot_revised"] = True
        fb = ""
    return accepted, log


# ------------------------------------------------------------------- [5] save (+ reground)
def reground_spec_record(rec, spec, full, first) -> dict:
    ak = spec.get("answer_key", {})
    return {
        "topic_id": rec["topic_id"], "status": rec.get("status", "KEPT"), "n": rec["n"],
        "secret_type": spec.get("secret_type", "lying"),
        "check": rec.get("check"),
        "answer": {
            "concealment": reground_text(spec.get("matter", ""), full),
            "actor": reground_text(spec["actor"], full),
            "victim": reground_text(spec["victim"], full),
            "true_fact": reground_text(ak.get("true_fact", ""), full),
            "false_belief": reground_text(ak.get("false_belief", ""), full),
        },
        "atoms": [{**a, "fact": reground_text(a.get("fact", ""), full)} for a in flatten_atoms(spec)],
        "clues": reground_clues(rec.get("clues", []), full, first),
        "_anchor": rec.get("_anchor"),          # held-out provenance: lets Stage-4 excise the real event cluster
    }


def render_readable(records) -> str:
    """Human-readable dump: per topic the SECRET, the PLOT (a1/a2/a3), and the clue EMAILS. Works on
    both the clue records (KEPT/DROP, real identities) and the spec records (--spec-only, Person A-J)."""
    out = []
    for r in records:
        spec = r.get("spec", {}) or {}
        topic = r.get("topic", {}) or {}
        atoms = r.get("atoms") or (flatten_atoms(spec) if spec else [])
        a = r.get("answer")
        if not a:                                           # spec-only / DROP: pull from spec + topic
            ak = spec.get("answer_key", {})
            a = {"concealment": spec.get("matter", "") or topic.get("secret", ""),
                 "actor": spec.get("actor", ""), "victim": spec.get("victim", ""),
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
        for at in atoms:
            out.append(f"  {at.get('id', '?')} [{at.get('role', '')}] {at.get('fact', '')}")
        out.append("")
        clues = r.get("clues", []) or []
        out.append(f"EMAILS ({len(clues)} clues)" if clues else "EMAILS: (none - spec-only or DROP)")
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


def _merge(path: Path, new_rows: dict):
    keep = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                r = json.loads(line); keep[r["topic_id"]] = r
    keep.update(new_rows)
    return [keep[k] for k in sorted(keep)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default="all")
    ap.add_argument("--n", type=int, default=2, help="clue emails per secret")
    ap.add_argument("--matrix", default="", help="per-topic n, e.g. 'T08:2,T02:3,T01:4' (overrides --topic/--n)")
    ap.add_argument("--engine", choices=["vllm", "api"], default="api",
                    help="vllm = ONE local model for gen/judge/probe (smoke test, separation-of-duties OFF)")
    ap.add_argument("--tp", type=int, default=2, help="tensor-parallel size for vllm")
    ap.add_argument("--budgets", default="3,5", help="email-retry budget, summed (plot is generated "
                    "ONCE; only the email step retries). '3,5' -> up to 8 email tries.")
    ap.add_argument("--plots", default="benchmark_pool/plot_generation.json")
    ap.add_argument("--specs-file", default="benchmark_pool/spec_generation.jsonl")
    ap.add_argument("--respec", action="store_true", help="ignore cached specs, regenerate fresh")
    ap.add_argument("--secret-type", default="lying",
                    help="loads prompts/spec_{generate,judge}_<type>.md (currently: lying)")
    ap.add_argument("--spec-only", action="store_true",
                    help="stop after spec gen+judge (test the checks; no render / AND-check)")
    ap.add_argument("--no-iterate", action="store_true",
                    help="ONE shot: render + run the AND-check once for its verdict, keep the emails "
                         "regardless of pass/fail (no diagnose/retry). For inspecting results cheaply.")
    ap.add_argument("--spec-iters", type=int, default=3)
    ap.add_argument("--gen-temp", type=float, default=0.4)
    ap.add_argument("--preset", default="or-claude-sonnet", help="generator (spec + clues)")
    ap.add_argument("--judge-preset", default="or-gpt-5", help="spec judge (cross-vendor)")
    ap.add_argument("--probe-presets", default="or-gpt-5,google/gemini-3.1-pro-preview",
                    help="JOINT blind-probers; joint recovers if ANY one does (each != generator)")
    ap.add_argument("--solo-probe-presets", default="or-gpt-5,google/gemini-3.1-pro-preview",
                    help="per-subset leak probers; a subset leaks if ANY one recovers it")
    ap.add_argument("--out", default="", help="default benchmark_pool/email_generation_n<n>.jsonl")
    args = ap.parse_args()

    budgets = [int(x) for x in args.budgets.split(",") if x.strip()]
    out = Path(args.out or ("benchmark_pool/smoke_spec.jsonl" if args.matrix
                            else f"benchmark_pool/email_generation_n{args.n}.jsonl"))
    sf = Path(args.specs_file)
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

    if args.engine == "vllm":
        eng = build_engine("vllm", args.preset, tp=args.tp)
        gen = jud = diag = eng
        joint = solo = [eng]
        print(f"LOCAL smoke: gen=judge=probe=diag = vllm:{args.preset} (tp={args.tp}) "
              f"— separation-of-duties OFF (plumbing test only)")
    else:
        gen = build_engine("api", args.preset)
        jud = build_engine("api", args.judge_preset)
        cache = {}

        def _eng(p):
            if p not in cache:
                cache[p] = build_engine("api", p)
            return cache[p]
        joint = [_eng(p.strip()) for p in args.probe_presets.split(",") if p.strip()]
        solo = [_eng(p.strip()) for p in args.solo_probe_presets.split(",") if p.strip()] or [joint[0]]
        diag = joint[0]

    spec_cache = {}
    if sf.exists() and not args.respec:
        for line in sf.read_text().splitlines():
            if line.strip():
                r = json.loads(line); spec_cache[r["topic_id"]] = r["spec"]
        print(f"loaded {len(spec_cache)} cached spec(s) from {sf}")

    rows, spec_rows, attempts, summary = {}, {}, [], []
    for tid, n in jobs:
        t0 = time.time()
        entry = kept[tid]
        era = (entry.get("anchor", {}).get("date", "") or "")[:7]
        spec = None if args.respec else spec_cache.get(tid)
        spec_log = []
        if not spec:
            spec, verdict, spec_log = make_spec(gen, jud, entry, relabel, team, args.spec_iters,
                                                args.gen_temp, args.secret_type)
        if not spec:
            print(f"  {tid}:n{n}: SPEC_FAIL (judge never passed)")
            attempts.append({"topic_id": tid, "n": n, "status": "SPEC_FAIL", "spec_log": spec_log})
            continue
        spec_cache[tid] = spec
        spec_rows[tid] = {"topic_id": tid, "topic": entry.get("topic"), "spec": spec}
        if args.spec_only:
            attempts.append({"topic_id": tid, "n": n, "status": "SPEC_PASS", "spec_log": spec_log})
            print(f"  {tid}:n{n}: SPEC_PASS  (a1/a2/a3)")
            continue
        plan, err = plan_distribution(spec, n)
        if err:
            print(f"  {tid}:n{n}: {err}")
            attempts.append({"topic_id": tid, "n": n, "status": "N_INFEASIBLE",
                             "note": err, "spec_log": spec_log})
            continue
        accepted, log = run_topic(gen, solo, joint, diag, spec, plan, team, n, era, budgets,
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
        anon = {"topic_id": tid, "n": n, "spec": spec, "plan": plan,
                "clues": clues, "status": status, "check": check,
                "_anchor": {"message_id": anc.get("message_id", ""),
                            "text": entry.get("anchor_full_body") or anc.get("snippet", "")}}
        key = f"{tid}_n{n}"
        rows[key] = (reground_spec_record(anon, spec, full_nm, first_nm) if clues
                     else {**anon, "atoms": flatten_atoms(spec)})
        attempts.append({"topic_id": tid, "n": n, "status": status, "plan": plan,
                         "spec_log": spec_log, "log": log})
        line = (f"  {tid}:n{n}: {status}  plan={[c['carries'] for c in plan]} "
                f"joint={check['joint']}  leaks={check['leaks']}  ({time.time()-t0:.0f}s)")
        print(line)
        summary.append(line.strip())

    out.parent.mkdir(parents=True, exist_ok=True)
    merged = _merge(out, rows)
    out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in merged) + "\n")
    merged_specs = _merge(sf, spec_rows)
    sf.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in merged_specs) + "\n")
    Path(str(out) + ".attempts.json").write_text(json.dumps(attempts, ensure_ascii=False, indent=2))

    rd = out.with_suffix(".txt")                            # readable: secret + plot (a1/a2/a3) + clue emails
    rd.write_text(render_readable(merged_specs if args.spec_only else merged))

    n_keep = sum(r.get("status") == "KEPT" for r in merged)
    print(f"\n{n_keep}/{len(merged)} KEPT  ->  {out}  (+ .attempts.json)  |  specs -> {sf}  |  readable -> {rd}")


if __name__ == "__main__":
    main()
