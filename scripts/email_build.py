#!/usr/bin/env python3
"""Email Generation (plot-grounded) — the finalized architecture.

  atomize           lean, must-have facts only; figures/detail stay in the PLOT      (prompts/email_atomize.md)
  distribute        write natural emails FROM the plot; atoms = per-clue assignment  (prompts/email_distribute.md)
  validate          blind solo + joint probe (reused from email_generate.py)
  diagnose          failure modes + one revision -> fed back into distribute
  budget schedule   attempt 1 runs N1 diagnose-iters; if it doesn't converge, RESTART fresh with N2
                    (feedback cleared); then stop. e.g. --budgets 3,5. Random restart beats grinding a
                    friction-stuck feedback chain.

Atoms serve two roles: the per-clue assignment skeleton and the acceptance checklist (MISSING_* in
diagnose). The PLOT carries the figures and contradictions; the emails are written from it.

  uv run python scripts/email_build.py --topic all --n 2 --budgets 3,5
  uv run python scripts/email_build.py --topic T07 --n 2      # single topic; merges into the n=2 file
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
from plot_assemble import load_plot_secrets, load_plot_topics, scrub_corp     # noqa: E402
from email_generate import (build_team, secret_block, render, extract_json,   # noqa: E402
                            validate, diagnose)
from reground import name_maps, reground_record                               # noqa: E402
from src.models.engine_factory import build_engine                            # noqa: E402

ATOMIZE = Path("prompts/email_atomize.md")
DISTRIBUTE = Path("prompts/email_distribute.md")


# ----------------------------------------------------------------------- generation steps
def atomize(eng, tid, sblock, plot) -> list:
    p = (ATOMIZE.read_text()
         .replace("<<SECRET>>", sblock).replace("<<PLOT>>", plot["plot"])
         .replace("<<ACTOR>>", plot["actor"]).replace("<<VICTIM>>", plot["victim"])
         .replace("<<TID>>", tid))
    return (extract_json(eng.generate(p, max_tokens=1200, temperature=0.3)[0]) or {}).get("atoms") or []


def distribute(eng, plot, atoms, team, era, n, feedback) -> list:
    ab = "\n".join(f"  {a['id']} [{a['role']}] {a['fact']}" for a in atoms)
    fb = (f"\n## REVISION NOTES — address these; keep every atom established and the emails natural:\n{feedback}\n"
          if feedback else "")
    p = (DISTRIBUTE.read_text()
         .replace("<<ACTOR>>", plot["actor"]).replace("<<VICTIM>>", plot["victim"])
         .replace("<<PLOT>>", plot["plot"]).replace("<<TEAM>>", team).replace("<<ATOMS>>", ab)
         .replace("<<N>>", str(n)).replace("<<ERA>>", era).replace("<<FEEDBACK>>", fb))
    clues = (extract_json(eng.generate(p, max_tokens=2600, temperature=0.5)[0]) or {}).get("clues") or []
    for c in clues:                                          # company never leaks through a body
        for m in c.get("messages", []):
            m["body"] = scrub_corp(m.get("body", "") or "")
            m["subject"] = scrub_corp(m.get("subject", "") or "")
    return clues


def _feedback(dx) -> str:
    ml = "; ".join(f"{m.get('mode')} ({m.get('where', '')})" for m in dx.get("modes", []))
    return (f"Failure modes: {ml}\nRevision: {dx.get('revision', '')}".strip()
            if (dx.get("modes") or dx.get("revision")) else
            "Revise the emails so the concealment is jointly recoverable and no clue leaks alone.")


def _base_subject(s: str) -> str:
    s = (s or "").lower().strip()
    while True:
        if s.startswith("re:"):
            s = s[3:].strip()
        elif s.startswith("fwd:"):
            s = s[4:].strip()
        elif s.startswith("fw:"):
            s = s[3:].strip()
        else:
            return s


def _embedded_turn(body: str) -> bool:
    """True if a body crams a second sender's turn into it (the model dodging the message-count cap):
    a bracketed stage direction, or a bare '---' separator not introducing a forward."""
    b = body or ""
    if re.search(r"\[[^\]]*(reply|appended|forwarded to|same thread)[^\]]*\]", b, re.I):
        return True
    for m in re.finditer(r"(?m)^\s*-{3,}\s*$", b):           # a line that is only dashes
        after = b[m.end():m.end() + 60].lower()
        if "forwarded" not in after and "original message" not in after:
            return True
    return False


def chain_violations(clues) -> list:
    """A clue must be ONE email thread: <= 2 messages on the same base subject, and each message body
    a single sender's email. Returns the clue indices that aren't."""
    bad = []
    for c in clues:
        msgs = c.get("messages", []) or []
        subs = {_base_subject(m.get("subject", "")) for m in msgs}
        if len(msgs) > 2 or len(subs) > 1 or any(_embedded_turn(m.get("body", "")) for m in msgs):
            bad.append(c.get("i"))
    return bad


ALLOWED_BRACKETS = {"[firm]", "[trading platform]", "[online trading platform]"}


def _msg_texts(m: dict) -> list:
    out = [m.get("subject", ""), m.get("body", "")]
    fwd = m.get("forward")
    if isinstance(fwd, dict):
        out += [fwd.get("subject", ""), fwd.get("body", "")]
    return out


def placeholder_violations(clues) -> list:
    """Only '[firm]' is an allowed placeholder. Flag clues with any other '[...]' token (e.g.
    '[counterparty]', '[remaining names …]') — those read as unfilled template fields."""
    bad = []
    for c in clues:
        hit = False
        for m in c.get("messages", []):
            for t in _msg_texts(m):
                if any(tok.lower() not in ALLOWED_BRACKETS for tok in re.findall(r"\[[^\]]+\]", t or "")):
                    hit = True
                    break
            if hit:
                break
        if hit:
            bad.append(c.get("i"))
    return bad


def letter_violations(clues) -> list:
    """People must be named by their full label 'Person X', not a bare letter. Flag a body with a
    bare-letter greeting/sign-off ('H —', a line that is just 'C', '— B') — those don't re-ground."""
    bad = []
    for c in clues:
        hit = False
        for m in c.get("messages", []):
            for ln in (m.get("body", "") or "").splitlines():
                s = ln.strip()
                if re.fullmatch(r"[—\-]?\s*[A-J]\s*[—,.\-]?", s) or re.match(r"^[A-J]\s*[—\-]\s", ln):
                    hit = True
                    break
            if hit:
                break
        if hit:
            bad.append(c.get("i"))
    return bad


def run_topic(gen, solo, joint, diag, plot, mt, atoms, n, budgets):
    """<= budgets[i] diagnose-iters per attempt; on non-convergence, RESTART fresh (feedback cleared)
    with the next budget; stop when the schedule is exhausted."""
    team, era = build_team(), mt.get("era") or "the period of the original events"
    accepted, log = None, []
    for attempt, budget in enumerate(budgets, 1):
        fb = ""
        for it in range(1, budget + 1):
            clues = distribute(gen, plot, atoms, team, era, n, fb)
            if not clues:
                log.append({"attempt": attempt, "iter": it, "ok": False, "clues": [],
                            "report": {"leaks": [], "joint_votes": 0, "n_joint": len(joint)}})
                fb = "Your previous output was not valid JSON. Return ONE object with a 'clues' array."
                continue
            ch, ph, lv = chain_violations(clues), placeholder_violations(clues), letter_violations(clues)
            if ch or ph or lv:                               # structural gate — skip the probes
                bad = sorted(set(ch) | set(ph) | set(lv))
                log.append({"attempt": attempt, "iter": it, "ok": False, "clues": clues,
                            "report": {"leaks": [], "joint_votes": 0, "n_joint": len(joint),
                                       "chain_bad": bad}})
                notes = []
                if ch:
                    notes.append("not one clean email thread — a clue is ONE thread of <= 2 emails on the "
                                 "same subject, each message one sender (no '---' or '[X reply]' embedded "
                                 "second turn); put the victim's reliance in their OWN reply and DESCRIBE "
                                 "any third-party action there ('clearing the desk on that basis'), never a "
                                 "separate email to that third party")
                if ph:
                    notes.append("contains a bracketed placeholder or list-abbreviation meta — only "
                                 "'[firm]' is allowed; write the counterparty as a natural phrase (the "
                                 "counterparty / its real name), no other '[...]' tokens")
                if lv:
                    notes.append("uses a bare single letter for a person (e.g. 'H —', a line that is just "
                                 "'C'); name EVERY person by their full label 'Person A'…'Person J' — in "
                                 "greetings, sign-offs and inline alike (write 'Person H,' and sign 'Person C')")
                fb = f"Clue(s) {bad} are invalid: " + "; ".join(notes) + ". Rewrite them clean."
                continue
            ok, report = validate(solo, joint, clues, plot)
            log.append({"attempt": attempt, "iter": it, "ok": ok, "clues": clues, "report": report})
            if ok:
                accepted = clues
                break
            dx = diagnose(diag, clues, atoms, plot, report)
            log[-1]["diagnosis"] = dx
            fb = _feedback(dx)
        if accepted:
            break
    return accepted, log


# ----------------------------------------------------------------------- readable
def build_readable(tid, plot, mt, atoms, log, accepted) -> str:
    L = [f"{tid}   [{'KEPT' if accepted else 'DROP'}]", "",
         "  --- ANSWER KEY ---",
         f"  concealment : {mt.get('secret', '')}",
         f"  true_fact   : {plot.get('true_fact', '')}",
         f"  false_belief: {plot.get('false_belief', '')}",
         f"  actor       : {plot.get('actor', '')}",
         f"  victim      : {plot.get('victim', '')}",
         f"  era         : {mt.get('era', '')}", "",
         f"  --- ATOMS ({len(atoms)}) ---"]
    L += [f"    {a['id']} [{a['role']}] {a['fact']}" for a in atoms]
    L += ["", "  --- ITERATIONS ---"]
    for e in log:
        rep = e.get("report", {})
        L.append(f"  a{e.get('attempt', 1)}.{e['iter']}: {'PASS' if e['ok'] else 'fail'}  "
                 f"leaks={rep.get('leaks')} joint={rep.get('joint_votes')}/{rep.get('n_joint')}")
        if e.get("diagnosis"):
            L.append(f"        modes={[m.get('mode') for m in e['diagnosis'].get('modes', [])]}")
    L += ["", "  --- FINAL CLUES ---"]
    for c in (accepted or (log[-1]["clues"] if log else [])):
        L.append(f"\n  CLUE {c.get('i')}")
        L.append(render(c.get("messages")))
    return "\n".join(L)


# ----------------------------------------------------------------------- driver
def _merge(path: Path, new_rows: dict):
    """Load existing JSONL keyed by topic_id, overwrite the run topics, keep the rest; return ordered list."""
    keep = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                keep[r["topic_id"]] = r
    keep.update(new_rows)
    return [keep[k] for k in sorted(keep)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default="all")
    ap.add_argument("--n", type=int, default=2, help="clue emails per secret")
    ap.add_argument("--budgets", default="3,5", help="fresh-restart iter budgets, e.g. 3,5")
    ap.add_argument("--plots", default="benchmark_pool/plot_generation.json")
    ap.add_argument("--atoms-file", default="benchmark_pool/email_generation_atoms.jsonl")
    ap.add_argument("--reatomize", action="store_true", help="ignore cached atoms, atomize fresh")
    ap.add_argument("--preset", default="or-claude-sonnet", help="generator")
    ap.add_argument("--probe-presets", default="or-gpt-5,x-ai/grok-4.3,google/gemini-3.1-pro-preview",
                    help="JOINT blind-probers (majority vote); each != generator")
    ap.add_argument("--solo-probe-presets", default="or-gpt-5", help="per-clue solo-leak probers")
    ap.add_argument("--out", default="", help="default benchmark_pool/email_generation_n<n>.jsonl")
    args = ap.parse_args()

    budgets = [int(x) for x in args.budgets.split(",") if x.strip()]
    out = Path(args.out or f"benchmark_pool/email_generation_n{args.n}.jsonl")
    af = Path(args.atoms_file)
    secrets = load_plot_secrets(args.plots)
    meta = load_plot_topics(args.plots)
    src_kept = {k["id"]: k for k in json.loads(Path(args.plots).read_text())["kept"]}
    full_nm, first_nm = name_maps()                       # for output-time re-grounding
    tids = list(secrets) if args.topic == "all" else [t for t in args.topic.split(",") if t in secrets]
    print(f"{len(tids)} topic(s): {', '.join(tids)}  |  n={args.n}  budgets={budgets}")

    gen = build_engine("api", args.preset)
    cache = {}
    def _eng(p):
        if p not in cache:
            cache[p] = build_engine("api", p)
        return cache[p]
    joint = [_eng(p.strip()) for p in args.probe_presets.split(",") if p.strip()]
    solo = [_eng(p.strip()) for p in args.solo_probe_presets.split(",") if p.strip()] or [joint[0]]
    diag = joint[0]

    atoms_cache = {}
    if af.exists() and not args.reatomize:
        for line in af.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                atoms_cache[r["topic_id"]] = r["atoms"]
        print(f"loaded {len(atoms_cache)} cached atom set(s) from {af}")

    rows, atoms_rows, attempts, summary = {}, {}, [], []
    for tid in tids:
        t0 = time.time()
        plot, mt = secrets[tid], meta.get(tid, {})
        sblock = secret_block(plot, mt)
        atoms = (None if args.reatomize else atoms_cache.get(tid)) or atomize(gen, tid, sblock, plot)
        atoms_cache[tid] = atoms
        accepted, log = run_topic(gen, solo, joint, diag, plot, mt, atoms, args.n, budgets)
        status = "KEPT" if accepted else "DROP"
        anon = {"topic_id": tid, "atoms": atoms, "clues": accepted or [], "status": status}
        # re-ground KEPT items to real Enron identities at save time (generation stayed anonymous)
        rows[tid] = reground_record(anon, src_kept[tid], full_nm, first_nm) if status == "KEPT" else anon
        atoms_rows[tid] = {"topic_id": tid, "atoms": atoms}      # anon cache stays anonymous
        attempts.append({"topic_id": tid, "status": status, "log": log})
        last = log[-1]["report"] if log else {}
        att = max((e.get("attempt", 1) for e in log), default=0)
        line = (f"  {tid}: {status}  attempts={att} gens={len(log)}  "
                f"joint={last.get('joint_votes')}/{last.get('n_joint')}  ({time.time()-t0:.0f}s)")
        print(line)
        summary.append(line.strip())

    # merge into canonical files (subset runs preserve other topics)
    out.parent.mkdir(parents=True, exist_ok=True)
    merged = _merge(out, rows)
    out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in merged) + "\n")
    merged_atoms = _merge(af, atoms_rows)
    af.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in merged_atoms) + "\n")
    Path(str(out) + ".attempts.json").write_text(json.dumps(attempts, ensure_ascii=False, indent=2))

    # human-readable companion via the canonical builder (reads the regrounded answer key)
    subprocess.run([sys.executable, "scripts/email_readable.py", "--clues", str(out),
                    "--source", args.plots, "--out", str(out).replace(".jsonl", ".txt")], check=False)

    n_keep = sum(r["status"] == "KEPT" for r in merged)
    print(f"\n{n_keep}/{len(merged)} KEPT  ->  {out}  (+ .txt, + .attempts.json)  |  atoms -> {af}")


if __name__ == "__main__":
    main()
