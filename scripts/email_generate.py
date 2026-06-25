#!/usr/bin/env python3
"""Step 3 — atomize once, then distribute into N clues with AND blind-validation + feedback.

Atomize ONCE per topic (cached to --atoms-file); the feedback loop only re-generates the EMAILS,
never the atoms.
  (1) ATOMIZE  — secret + plot -> role-tagged atoms {true_state, knew, gain, false_assurance,
                 reliance}. Cached; reused across runs and across --n.
  (2) LOOP (<= --max-iters):
        distribute the fixed atoms into N clue emails                    (gen model)
        -> voice-rewrite each clue in its sender's style                 (gen model)
        -> AND blind-validation by an ENSEMBLE of probers (majority vote) (probe models)
        pass -> keep ; fail -> DIAGNOSE (failure modes + one overall revision), insert the
        revision into the distribute prompt, and RE-GENERATE THE EMAILS. The atoms never change:
        a MISSING_* mode means an existing atom wasn't written into any email, so the fix is to
        write it in — an email-generation fix, not a new atom.

Ensemble: a prober blind-reads emails, then the matcher (same model, fed the intended secret) says
whether the read recovered it. The SOLO leak test (run per-clue, the costly axis) uses a small
prober set — by default one model; the JOINT recovery test runs the full ensemble with a majority
vote. A clue "leaks" / the joint "recovers" iff a majority of that test's probers say so. Probers
never include the generator (separation of duties).

Every topic — KEPT or DROPPED — is written to --out with a `status` field.

Usage:
  uv run python scripts/email_generate.py --n 2 \
      --engine api --preset or-claude-sonnet \
      --probe-engine api \
      --probe-presets or-gpt-5,x-ai/grok-4.3,google/gemini-3.1-pro-preview \
      --solo-probe-presets or-gpt-5 \
      --out benchmark_pool/email_generation_n2.jsonl
"""
from __future__ import annotations
import argparse
import itertools
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))          # for plot_assemble helpers

from plot_assemble import (load_plot_secrets, load_plot_topics, make_relabel, scrub_corp)
from src.models.engine_factory import build_engine

ATOMIZE_TMPL = Path("prompts/clue_atomize.md")
DISTRIB_TMPL = Path("prompts/clue_distribute.md")
VOICE_TMPL = Path("prompts/email_voice.md")
PROBE_TMPL = Path("prompts/email_probe.md")
MATCH_TMPL = Path("prompts/email_match.md")
DIAGNOSE_TMPL = Path("prompts/email_diagnose.md")


# ----------------------------------------------------------------------------- helpers
def extract_json(text: str) -> dict | None:
    t = re.sub(r"```$", "", re.sub(r"^```(?:json)?", "", text.strip()).strip()).strip()
    a, b = t.find("{"), t.rfind("}")
    if a == -1 or b == -1 or b < a:
        return None
    try:
        return json.loads(t[a:b + 1])
    except json.JSONDecodeError:
        return None


def render(messages: list[dict]) -> str:
    blocks = []
    for m in messages or []:
        to = ", ".join(m.get("to", []) or [])
        cc = ", ".join(m.get("cc", []) or [])
        hdr = f"From: {m.get('from', '?')}   To: {to}" + (f"   Cc: {cc}" if cc else "")
        hdr += f"   ({m.get('date', '')})\nSubject: {m.get('subject', '')}"
        blocks.append(hdr + "\n\n" + (m.get("body", "") or ""))
    return "\n\n========================================\n\n".join(blocks)


def build_team() -> str:
    people = json.loads(Path("benchmark_pool/people.json").read_text())
    P, AUTH = people["people"], people["authority"]
    parts = [f"- {p['label']} — {p['role']}" for p in P]
    parts += ["", "Authority:"] + [f"- {e['from']} {e['rel']} {e['to']}" for e in AUTH]
    return "\n".join(parts)


def secret_block(plot: dict, meta: dict) -> str:
    return (f"the concealment:                    {meta.get('secret', '')}\n"
            f"what is actually true:              {plot['true_fact']}\n"
            f"what the victim is led to believe:  {plot['false_belief']}\n"
            f"either / or:                        {meta.get('either_or', '')}")


def load_cards() -> dict:
    """label -> persona_card (relabeled + company-scrubbed); '' if no profile on disk."""
    people = json.loads(Path("benchmark_pool/people.json").read_text())["people"]
    relabel = make_relabel(people)
    cards = {}
    for p in people:
        pf = Path("profiles") / (p["real_name"].lower().replace(" ", ".") + ".json")
        card = ""
        if pf.exists():
            card = relabel(scrub_corp(json.loads(pf.read_text()).get("persona_card", ""))).strip()
        cards[p["label"]] = card
    return cards


# ----------------------------------------------------------------------- phase 1: atomize
def atomize(engine, tid, sblock, plot, feedback="") -> list[dict]:
    prompt = (ATOMIZE_TMPL.read_text()
              .replace("<<SECRET>>", sblock)
              .replace("<<ACTOR>>", plot["actor"])
              .replace("<<VICTIM>>", plot["victim"])
              .replace("<<PLOT>>", plot["plot"])
              .replace("<<TID>>", tid))
    prompt = scrub_corp(prompt) + (("\n\n## REVISE THE ATOMS\n" + feedback) if feedback else "")
    out = extract_json(engine.generate(prompt, max_tokens=1500, temperature=0.3)[0])
    return (out or {}).get("atoms") or []


# -------------------------------------------------------------- phase 2: distribute + write
def distribute(engine, tid, sblock, plot, atoms, team, era, n, feedback="") -> list[dict]:
    atoms_block = "\n".join(f"{a['id']} [{a['role']}] {a['fact']}" for a in atoms)
    prompt = (DISTRIB_TMPL.read_text()
              .replace("<<SECRET>>", sblock)
              .replace("<<ACTOR>>", plot["actor"])
              .replace("<<VICTIM>>", plot["victim"])
              .replace("<<PLOT>>", plot["plot"])
              .replace("<<ATOMS>>", atoms_block)
              .replace("<<TEAM>>", team)
              .replace("<<ERA>>", era)
              .replace("<<N>>", str(n))
              .replace("<<TID>>", tid))
    prompt = scrub_corp(prompt) + (("\n\n## REVISE\n" + feedback) if feedback else "")
    out = extract_json(engine.generate(prompt, max_tokens=3500, temperature=0.5)[0])
    return (out or {}).get("clues") or []


def voice_rewrite(engine, clue, atoms_by_id, cards) -> dict:
    """Re-render a clue's bodies in each sender's voice; headers stay, only bodies change.
    Bodies are company-scrubbed after rewrite. On any hiccup the clue is returned unchanged."""
    msgs = clue.get("messages") or []
    if not msgs:
        return clue
    senders = [m.get("from", "?") for m in msgs]
    voices = "\n".join(f"{s}: {cards.get(s) or '(no notes — keep it plain and businesslike)'}"
                       for s in dict.fromkeys(senders))
    facts = [atoms_by_id[cid]["fact"] for cid in clue.get("carries", []) if cid in atoms_by_id]
    atoms_block = "\n".join(f"- {f}" for f in facts) or "- (preserve every fact already here)"
    prompt = (VOICE_TMPL.read_text()
              .replace("<<VOICES>>", voices)
              .replace("<<EMAILS>>", render(msgs))
              .replace("<<ATOMS>>", atoms_block))
    out = extract_json(engine.generate(prompt, max_tokens=1500, temperature=0.4)[0])
    new_msgs = (out or {}).get("messages")
    if new_msgs and len(new_msgs) == len(msgs):
        for orig, nw in zip(msgs, new_msgs):
            if isinstance(nw, dict) and nw.get("body"):
                orig["body"] = nw["body"]
    for m in msgs:                                       # company never leaks through the body
        m["body"] = scrub_corp(m.get("body", ""))
        m["subject"] = scrub_corp(m.get("subject", ""))
    return clue


# ----------------------------------------------------------- phase 4: ensemble AND-validation
def probe(engine, emails_text):
    p = PROBE_TMPL.read_text().replace("<<EMAILS>>", emails_text)
    # high cap so REASONING probers (emit visible chain-of-thought before the JSON) aren't
    # truncated; non-reasoning probers stop early so their cost is unchanged.
    return extract_json(engine.generate(p, max_tokens=3000, temperature=0.0)[0])


def match(engine, intended, probe_json):
    p = (MATCH_TMPL.read_text()
         .replace("<<ACTOR>>", intended["actor"]).replace("<<VICTIM>>", intended["victim"])
         .replace("<<TRUE>>", intended["true_fact"]).replace("<<FALSE>>", intended["false_belief"])
         .replace("<<PROBE>>", json.dumps(probe_json, ensure_ascii=False)))
    return extract_json(engine.generate(p, max_tokens=1500, temperature=0.0)[0])


def recovers(engine, intended, msgs) -> tuple[bool, dict]:
    """Does this prober, blind, recover the intended concealment from these emails?"""
    pr = probe(engine, render(msgs))
    m = match(engine, intended, pr) if (pr and pr.get("hidden")) else None
    return bool(m and m.get("match")), {"probe": pr, "match": m}


def validate(solo_engines, joint_engines, clues, intended) -> tuple[bool, dict]:
    """A clue set is AND-valid iff NO PROPER SUBSET of the clues reveals the concealment on its own —
    every singleton, every pair, … every all-but-one — AND the FULL set is jointly recoverable. So a
    non-load-bearing clue (one the others already give away without) can't slip through.

    The per-subset leak test runs the (smaller) SOLO prober set; the JOINT test runs the full
    ensemble. A subset "leaks" / the joint "recovers" iff a majority of that test's probers recover
    the INTENDED concealment. For n=2 the proper subsets are just the two singletons (so it's
    unchanged); for n>=3 every pair / all-but-one is also probed."""
    maj_s, maj_j = len(solo_engines) // 2 + 1, len(joint_engines) // 2 + 1
    n = len(clues)

    subsets, leaks = [], []
    for r in range(1, n):                                  # proper subsets, size 1 .. n-1
        for combo in itertools.combinations(range(n), r):
            msgs = sorted((m for i in combo for m in (clues[i].get("messages") or [])),
                          key=lambda m: m.get("date", ""))
            votes, det = 0, []
            for e in solo_engines:
                ok, info = recovers(e, intended, msgs)
                det.append({**info, "recovered": ok}); votes += int(ok)
            ids = [clues[i].get("i") for i in combo]
            leaked = votes >= maj_s
            subsets.append({"subset": ids, "size": r, "leak_votes": votes, "leaked": leaked,
                            "probers": det})
            if leaked:
                leaks.append(ids)

    all_msgs = sorted((m for c in clues for m in (c.get("messages") or [])),
                      key=lambda m: m.get("date", ""))
    jvotes, jdet = 0, []
    for e in joint_engines:
        ok, info = recovers(e, intended, all_msgs)
        jdet.append({**info, "recovered": ok}); jvotes += int(ok)
    joint_ok = jvotes >= maj_j

    report = {"n_solo": len(solo_engines), "n_joint": len(joint_engines), "solo_majority": maj_s,
              "joint_majority": maj_j, "subsets": subsets, "leaks": leaks, "joint_votes": jvotes,
              "joint_ok": joint_ok, "joint_probers": jdet}
    return (not leaks and joint_ok), report


def _plabel(s):
    m = re.search(r"Person [A-J]", s or ""); return m.group(0) if m else ""


def _clues_block(clues, atoms):
    roles = {a["id"]: a["role"] for a in atoms}
    out = ["ATOMS:"] + [f"  {a['id']} [{a['role']}] {a['fact']}" for a in atoms]
    for c in clues:
        car = ", ".join(f"{x}:{roles.get(x, '?')}" for x in c.get("carries", []))
        out += [f"\nCLUE {c.get('i')} carries [{car}]:", render(c.get("messages"))]
    return "\n".join(out)


def diagnose(engine, clues, atoms, intended, report) -> dict:
    """One secret-aware call: which failure modes apply (from the 8) + one overall revision
    (failure reason + how to revise the clues). Returns {recovered, modes, revision}."""
    joint = [{k: (p.get("probe") or {}).get(k, "") for k in ("who", "whom", "about")}
             for p in report.get("joint_probers", [])]
    leaks = report.get("leaks") or []
    leakage = (f"These clue subset(s) already reveal the secret without the rest, so a clue isn't "
               f"load-bearing: {leaks}. Make each listed subset insufficient on its own."
               if leaks else "No single clue or proper subset reveals the secret.")
    p = (DIAGNOSE_TMPL.read_text()
         .replace("<<ACTOR>>", intended["actor"]).replace("<<VICTIM>>", intended["victim"])
         .replace("<<TRUE>>", intended["true_fact"]).replace("<<FALSE>>", intended["false_belief"])
         .replace("<<VICTIM_LABEL>>", _plabel(intended["victim"]))
         .replace("<<CLUES>>", _clues_block(clues, atoms))
         .replace("<<JOINT>>", json.dumps(joint, ensure_ascii=False))
         .replace("<<LEAKAGE>>", leakage))
    return extract_json(engine.generate(p, max_tokens=2500, temperature=0.0)[0]) or {}


# --------------------------------------------------------------------------------- driver
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default="all")
    ap.add_argument("--secrets", default="benchmark_pool/plot_generation.json")
    ap.add_argument("--topics", default="benchmark_pool/plot_generation.json")
    ap.add_argument("--n", type=int, default=2, help="clues to split each secret into")
    ap.add_argument("--engine", choices=["vllm", "api"], default="api")
    ap.add_argument("--preset", default="or-claude-sonnet", help="generator model")
    ap.add_argument("--probe-engine", choices=["vllm", "api"], default="api")
    ap.add_argument("--probe-presets", default="or-gpt-5",
                    help="comma list of JOINT blind-probers (majority vote); each must != generator")
    ap.add_argument("--solo-probe-presets", default="",
                    help="probers for the per-clue solo-leak test (default: first of --probe-presets)")
    ap.add_argument("--diagnose-preset", default="",
                    help="secret-aware diagnoser (modes + revision); default: first of --probe-presets")
    ap.add_argument("--tp", type=int, default=4)
    ap.add_argument("--max-iters", type=int, default=3)
    ap.add_argument("--atoms-file", default="benchmark_pool/email_generation_atoms.jsonl")
    ap.add_argument("--reatomize", action="store_true", help="ignore cached atoms, atomize fresh")
    ap.add_argument("--out", default="benchmark_pool/email_generation_n2.jsonl")
    args = ap.parse_args()

    secrets = load_plot_secrets(args.secrets)
    meta = load_plot_topics(args.topics)
    tids = list(secrets) if args.topic == "all" else [args.topic]
    tids = [t for t in tids if t in secrets]
    print(f"{len(tids)} topic(s): {', '.join(tids)}  |  n={args.n}")

    gen_engine = build_engine(args.engine, args.preset, args.tp)
    joint_presets = [p.strip() for p in args.probe_presets.split(",") if p.strip()]
    solo_presets = ([p.strip() for p in args.solo_probe_presets.split(",") if p.strip()]
                    if args.solo_probe_presets else joint_presets[:1])
    _cache = {}

    def _eng(p):
        if p not in _cache:
            _cache[p] = build_engine(args.probe_engine, p, args.tp)
        return _cache[p]
    joint_engines = [_eng(p) for p in joint_presets]
    solo_engines = [_eng(p) for p in solo_presets]
    diag_preset = args.diagnose_preset or joint_presets[0]
    diag_engine = _eng(diag_preset)
    print(f"gen: {args.engine}:{args.preset}")
    print(f"  solo-leak probers ({len(solo_engines)}): {', '.join(solo_presets)}")
    print(f"  joint probers (majority {len(joint_engines)//2+1}/{len(joint_engines)}): "
          f"{', '.join(joint_presets)}")
    print(f"  diagnoser: {diag_preset}")

    atoms_cache = {}
    af = Path(args.atoms_file)
    if af.exists() and not args.reatomize:
        for l in af.read_text().splitlines():
            if l.strip():
                r = json.loads(l); atoms_cache[r["topic_id"]] = r["atoms"]
        print(f"loaded {len(atoms_cache)} cached atom set(s) from {af}")

    team = build_team()
    cards = load_cards()
    results, logs = [], []
    for tid in tids:
        plot, mt = secrets[tid], meta.get(tid, {})
        sblock = secret_block(plot, mt)
        era = mt.get("era") or "the period of the original events"
        # atomize ONCE (cache on disk); the loop below never re-atomizes — it only re-generates emails.
        atoms = None if args.reatomize else atoms_cache.get(tid)
        if not atoms:
            atoms = atomize(gen_engine, tid, sblock, plot)
            if atoms:
                atoms_cache[tid] = atoms
        atoms_by_id = {a.get("id"): a for a in (atoms or [])}
        dist_fb, accepted, attempts = "", None, []
        for it in range(1, args.max_iters + 1):
            if not atoms:
                attempts.append({"iter": it, "result": "atomize_fail"})
                print(f"  {tid}: atomize_fail"); break
            clues = distribute(gen_engine, tid, sblock, plot, atoms, team, era, args.n, dist_fb)
            if not clues:
                attempts.append({"iter": it, "result": "parse_fail"})
                dist_fb = "Your previous output was not valid JSON. Return ONE object with a 'clues' array."
                print(f"  {tid} iter{it}: parse_fail"); continue
            clues = [voice_rewrite(gen_engine, c, atoms_by_id, cards) for c in clues]
            ok, report = validate(solo_engines, joint_engines, clues, plot)
            rec = {"topic_id": tid, "atoms": atoms, "clues": clues}
            attempts.append({"iter": it, "result": "PASS" if ok else "fail",
                             "clues": rec, "report": report})
            print(f"  {tid} iter{it}: {'PASS' if ok else 'fail'}  leaks={report['leaks']} "
                  f"joint={report['joint_votes']}/{report['n_joint']}")
            if ok:
                accepted = rec; break
            # diagnose (failure modes + one overall revision) -> feed BOTH the modes and the
            # revision into the NEXT email-generation pass. Atoms are fixed; only the emails change.
            dx = diagnose(diag_engine, clues, atoms, plot, report)
            attempts[-1]["diagnosis"] = dx
            ms = dx.get("modes", [])
            print(f"        diagnose: modes={[m.get('mode') for m in ms]}")
            mode_lines = "; ".join(f"{m.get('mode')} ({m.get('where', '')})" for m in ms)
            dist_fb = (f"Failure modes: {mode_lines}\nRevision: {dx.get('revision', '')}".strip()
                       if (ms or dx.get("revision")) else
                       "Revise the emails so the concealment is jointly recoverable and no clue leaks alone.")

        last = accepted or (attempts[-1].get("clues") if attempts and "clues" in attempts[-1]
                            else {"topic_id": tid, "atoms": atoms or [], "clues": []})
        last = {**last, "status": "KEPT" if accepted else "DROP"}
        results.append(last)
        logs.append({"topic_id": tid, "status": last["status"], "iters": len(attempts),
                     "attempts": attempts})
        print(f"  -> {tid} {last['status']} after {len(attempts)} iter(s)\n")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as fh:
        for r in results:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with af.open("w") as fh:
        for tid, ats in atoms_cache.items():
            fh.write(json.dumps({"topic_id": tid, "atoms": ats}, ensure_ascii=False) + "\n")
    Path(str(out) + ".attempts.json").write_text(json.dumps(logs, indent=2, ensure_ascii=False))
    n_keep = sum(r["status"] == "KEPT" for r in results)
    print(f"WROTE {out} ({n_keep}/{len(results)} KEPT) | atoms -> {af} | log -> {out}.attempts.json")


if __name__ == "__main__":
    main()
