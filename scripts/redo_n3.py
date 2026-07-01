#!/usr/bin/env python3
"""Regenerate specific topics at GENUINE n=3 ([a1][a2][a3]) with the current plot-iteration pipeline.

The n3_kept file carries T02/T05/T08 as the n=2 fallback ([a1,a2][a3]) — they never passed a real
3-clue split. This driver retries them at n=3 using real cross-vendor separation of duties
(Sonnet gen / GPT-5 + Gemini probe+diagnose), pulling era from the SPEC (topics anchor.date is a
1980 corpus artifact for T02). Writes a TEMP file — does not touch emails_lying_n3_kept.jsonl.

  uv run python scripts/redo_n3.py T02
  uv run python scripts/redo_n3.py T02 T05 T08 --budgets 3,5
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, "scripts")
sys.path.insert(0, ".")
import spec_build as sb
from reground import name_maps
from src.models.engine_factory import build_engine

ap = argparse.ArgumentParser()
ap.add_argument("topics", nargs="+")
ap.add_argument("--budgets", default="3,5")
ap.add_argument("--out", default="benchmark_pool/emails_lying_n3_redo.jsonl")
args = ap.parse_args()
budgets = [int(x) for x in args.budgets.split(",") if x.strip()]

specs = {json.loads(l)["topic_id"]: json.loads(l)["spec"]
         for l in open("benchmark_pool/specs_lying.jsonl") if l.strip()}
kept = {k["id"]: k for k in json.load(open("benchmark_pool/topics_lying.json"))["kept"]}
people = json.load(open("benchmark_pool/people.json"))
P, AUTH = people["people"], people["authority"]
team = "\n".join(["Team:"] + [f"- {p['label']} — {p['role']}" for p in P]
                 + ["", "Authority:"] + [f"- {e['from']} {e['rel']} {e['to']}" for e in AUTH])
full_nm, first_nm = name_maps()

gen = build_engine("api", "or-claude-sonnet")
jud = build_engine("api", "or-gpt-5")
cache = {}
def _eng(p):
    cache.setdefault(p, build_engine("api", p))
    return cache[p]
joint = [_eng("or-gpt-5"), _eng("google/gemini-3.1-pro-preview")]
solo = joint
diag = joint[0]

print(f"REDO n=3 for {args.topics}  budgets={budgets}  (gen=sonnet, probe=gpt-5+gemini)", flush=True)
rows = []
for tid in args.topics:
    t0 = time.time()
    spec, entry = specs[tid], kept[tid]
    era = spec.get("era") or (entry.get("anchor", {}).get("date", "") or "")[:7]
    plan, err = sb.plan_distribution(spec, 3)
    if err:
        print(f"{tid}: {err}", flush=True)
        continue
    accepted, log = sb.run_topic(gen, solo, joint, diag, spec, plan, team, 3, era, budgets, iterate=True)
    last = log[-1] if log else {}
    rep = last.get("report", {})
    clues = accepted or last.get("clues", [])
    status = "KEPT" if accepted else "DROP"
    check = {"joint": f"{rep.get('joint_votes')}/{rep.get('n_joint')}", "leaks": rep.get("leaks", [])}
    anc = entry.get("anchor", {}) or {}
    anon = {"topic_id": tid, "n": 3, "spec": spec, "plan": plan, "clues": clues,
            "status": status, "check": check,
            "_anchor": {"message_id": anc.get("message_id", ""),
                        "text": entry.get("anchor_full_body") or anc.get("snippet", "")}}
    row = sb.reground_spec_record(anon, spec, full_nm, first_nm) if clues else \
        {**anon, "atoms": sb.flatten_atoms(spec)}
    rows.append(row)
    print(f"{tid}: {status}  plan={[c['carries'] for c in plan]}  joint={check['joint']}  "
          f"leaks={check['leaks']}  iters={len(log)}  ({time.time()-t0:.0f}s)", flush=True)

out = Path(args.out)
existing = {json.loads(l)["topic_id"]: json.loads(l) for l in out.read_text().splitlines()
            if l.strip()} if out.exists() else {}
for r in rows:
    existing[r["topic_id"]] = r
merged = list(existing.values())
out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in merged) + "\n")
out.with_suffix(".txt").write_text(sb.render_readable(merged))
print(f"\nWROTE {out}  ({len(rows)} redone, {len(merged)} total)  readable -> {out.with_suffix('.txt')}",
      flush=True)
