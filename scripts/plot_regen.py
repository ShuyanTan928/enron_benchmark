#!/usr/bin/env python3
"""Regenerate the observable-only PLOT for each already-curated topic, reusing its anchor — then
re-run the check1-7 plot judge. Keeps the 10 hand-curated secrets/anchors; only the plot NARRATION
is rewritten to the observable-surface form (no mind / motive / conclusion — those live in the
answer key). A topic is updated only if its new plot PASSES every check; if it never passes within
--max-iters its OLD plot is retained and flagged, so a secret is never silently lost.

Generation and judging are different models (separation of duties). Reuses the same plot prompt and
judge as the from-scratch pipeline (prompts/secret_plot_from_carrier.md + plot_iterate.judge).

  uv run python scripts/plot_regen.py                      # all topics, API gen+judge, write in place
  uv run python scripts/plot_regen.py --topic T09 --out benchmark_pool/plot_regen_preview.json
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from plot_assemble import make_relabel, scrub_corp                                  # noqa: E402
from plot_iterate import context_of, judge, all_pass, feedback_from, extract_json, CRITERIA  # noqa: E402
from src.models.engine_factory import build_engine                                  # noqa: E402

PROMPT = Path("prompts/secret_plot_from_carrier.md")


def build_prompt(entry: dict, relabel, team: str) -> str:
    """Fill the observable-plot prompt from a curated kept entry (reusing its real anchor)."""
    t = entry["topic"]
    topic_json = json.dumps({"id": entry["id"], "name": t.get("name", ""),
                             "secret": t.get("secret", ""), "either_or": t.get("either_or", "")},
                            indent=2, ensure_ascii=False)
    a = entry["anchor"]
    body = entry.get("anchor_full_body") or a.get("snippet", "")
    to = ", ".join(relabel(x) for x in a.get("to", [])) or "(internal)"
    anchor_block = (f'From: {relabel(a["from"])}  ->  To: {to}   ({(a.get("date","") or "")[:10]})\n'
                    f'Subject: "{relabel(a.get("subject",""))}"\n\n{relabel(body)}')
    return scrub_corp(PROMPT.read_text()
                      .replace("<<TOPIC>>", topic_json).replace("<<ANCHOR>>", anchor_block)
                      .replace("<<RELATIONSHIPS>>", team).replace("<<TID>>", entry["id"]))


def regen_one(gen, jud, entry, relabel, team, max_iters, gen_temp):
    """Generate -> judge -> feedback loop on a fixed anchor. Returns (plot|None, verdict|None, log)."""
    base = build_prompt(entry, relabel, team)
    ctx = context_of(base)
    prompt, log = base, []
    for it in range(1, max_iters + 1):
        cand = extract_json(gen.generate(prompt, max_tokens=2600, temperature=gen_temp)[0])
        if not cand or not cand.get("plot"):
            log.append({"iter": it, "result": "parse_fail"})
            prompt = base + "\n\n## CORRECTION\nReturn ONLY the JSON object."
            continue
        v, _ = judge(jud, ctx, cand)
        ok = all_pass(v)
        log.append({"iter": it, "result": "PASS" if ok else "fail",
                    "verdicts": {c: (v.get(c) or {}).get("verdict") for c in CRITERIA} if v else None})
        if ok:
            return cand, v, log
        prompt = base if v is None else base + "\n\n## CORRECTION REQUIRED\n" + feedback_from(v)
    return None, None, log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plots", default="benchmark_pool/plot_generation.json")
    ap.add_argument("--out", default="benchmark_pool/plot_generation.json")
    ap.add_argument("--topic", default="all")
    ap.add_argument("--gen-engine", choices=["vllm", "api"], default="api")
    ap.add_argument("--gen-preset", default="or-claude-sonnet")
    ap.add_argument("--judge-engine", choices=["vllm", "api"], default="api")
    ap.add_argument("--judge-preset", default="or-gpt-5")
    ap.add_argument("--tp", type=int, default=2)
    ap.add_argument("--max-iters", type=int, default=3)
    ap.add_argument("--gen-temp", type=float, default=0.4)
    args = ap.parse_args()

    doc = json.loads(Path(args.plots).read_text())
    people = json.loads(Path("benchmark_pool/people.json").read_text())
    P, AUTH = people["people"], people["authority"]
    relabel = make_relabel(P)
    team = "\n".join(["Team:"] + [f"- {p['label']} — {p['role']}" for p in P]
                     + ["", "Authority:"] + [f"- {e['from']} {e['rel']} {e['to']}" for e in AUTH])

    gen = build_engine(args.gen_engine, args.gen_preset, tp=args.tp)
    jud = build_engine(args.judge_engine, args.judge_preset, tp=args.tp)
    print(f"gen={args.gen_preset}  judge={args.judge_preset}  (separation of duties)")

    logs, n_ok = [], 0
    for entry in doc.get("kept", []):
        tid = entry["id"]
        if args.topic != "all" and tid != args.topic:
            continue
        plot, verdict, log = regen_one(gen, jud, entry, relabel, team, args.max_iters, args.gen_temp)
        if plot:
            entry["plot"] = plot                      # swap in the observable plot
            entry["judge"] = verdict
            entry.pop("regen_status", None)
            n_ok += 1
            print(f"  {tid}: PASS — observable plot in ({len(log)} iter)")
        else:
            entry["regen_status"] = "regen_failed_kept_old"   # never lose the secret; flag it
            print(f"  {tid}: FAIL after {len(log)} iter — OLD plot retained, flagged")
        logs.append({"topic_id": tid, "ok": bool(plot), "log": log})

    Path(args.out).write_text(json.dumps(doc, ensure_ascii=False, indent=2))
    Path(str(args.out) + ".regen.json").write_text(json.dumps(logs, ensure_ascii=False, indent=2))
    n_total = len(logs)
    print(f"\n{n_ok}/{n_total} regenerated to observable + judged PASS  ->  {args.out}")
    if n_ok < n_total:
        print("  (topics that failed kept their OLD plot, marked regen_status — review before batch)")


if __name__ == "__main__":
    main()
