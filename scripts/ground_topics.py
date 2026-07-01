"""Step 1 driver — over-generate grounded topic PROPOSALS for final rubric review.

For each proposal: gen_topic (gemma4-31B) -> HyDE -> BM25/RRF retrieve -> fit-judge.
Grounded proposals (judge picked a real anchor email) are kept; dup/NONE are discarded
and retried. The output is a proposals file; the final 10 (9 work / 1 casual) are chosen
by a separate rubric review — this script does not finalize the pool.

Usage:
  uv run python scripts/ground_topics.py --n_work 12 --n_casual 3
  uv run python scripts/ground_topics.py --n_work 1 --n_casual 0   # smoke test (one topic)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# CUDA_VISIBLE_DEVICES must be set before vllm/torch import.
def _early_gpus(default="0,1"):
    gpus = default
    for i, a in enumerate(sys.argv):
        if a == "--gpus" and i + 1 < len(sys.argv):
            gpus = sys.argv[i + 1]
        elif a.startswith("--gpus="):
            gpus = a.split("=", 1)[1]
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", gpus)

_early_gpus()
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.engine_factory import build_engine                  # noqa: E402
from src.grounding.corpus import load_emails                            # noqa: E402
from src.grounding.retrieval import HybridRetriever                     # noqa: E402
from src.grounding.pipeline import propose_topic                        # noqa: E402


def run_category(engine, retriever, emails, category, target, accepted, discarded,
                 max_fails, checker=None, used_anchors=None, secret_type=""):
    """Write `target` topics for this category. Successes do NOT count against the budget:
    we keep going until `target` are written OR `max_fails` attempts have FAILED (dup / NONE /
    CHECK-reject). So the most attempts this ever makes is target + max_fails.

    checker=None (manual)  : keep every grounded candidate (the CHECK is applied later,
                             by a human/Sonnet, over the dumped pending pool).
    checker given (sonnet) : apply the gate inline — ONE topic at a time:
                             generate -> ground -> CHECK -> if write, keep; if regenerate,
                             record it as rejected (so it is also avoided) and loop to the
                             next topic. This is the production (API) structure."""
    kept = []
    rejected: list[dict] = []          # this-run rejects, also fed to the AVOID list
    used_anchors = used_anchors if used_anchors is not None else set()
    fails = 0
    while len(kept) < target and fails < max_fails:
        p = propose_topic(engine, retriever, emails, category, accepted + rejected,
                          used_anchors=used_anchors, secret_type=secret_type)
        st = p["status"]
        topic = p.get("topic")
        name = (topic or {}).get("name", "?")
        if st != "grounded":
            fails += 1
            discarded.append(p)
            if topic:
                rejected.append(p.get("abstract_topic") or topic)
            print(f"  [{category} fail {fails}/{max_fails}] {st.upper():11} «{name}»")
            continue

        a = p["anchor"]
        if checker is not None:
            v = checker.check(p)
            p["check"] = v
            if v["decision"] != "write":
                fails += 1
                p["status"] = "check_reject"
                discarded.append(p)
                rejected.append(p.get("abstract_topic") or topic)            # avoid re-proposing this rejected idea
                print(f"  [{category} fail {fails}/{max_fails}] CHECK-REJECT «{name}»  ({v['reason'][:70]})")
                continue
            print(f"  [{category} {len(kept)+1}/{target}] CHECK-WRITE  «{name}»  -> {a['date'][:10]} \"{a['subject'][:38]}\"")
        else:
            print(f"  [{category} {len(kept)+1}/{target}] GROUNDED    «{name}»  -> {a['date'][:10]} \"{a['subject'][:38]}\"")
        kept.append(p)
        accepted.append(p.get("abstract_topic") or p["topic"])   # AVOID on the skeleton, not specifics
        mid = (p.get("anchor") or {}).get("message_id")
        if mid:
            used_anchors.add(mid)               # this anchor is now spent
    return kept


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["vllm", "api"], default="vllm",
                    help="generator backend: vllm=local gemma; api=pinned closed model (reproducible)")
    ap.add_argument("--preset", default="gemma4-31b")
    ap.add_argument("--gpus", default="0,1")
    ap.add_argument("--tp", type=int, default=2)
    ap.add_argument("--gpu_mem", type=float, default=0.9)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--n_work", type=int, default=12)
    ap.add_argument("--n_casual", type=int, default=3)
    ap.add_argument("--max-fails", type=int, default=30,
                    help="stop a category after this many FAILED attempts (dup / NONE / "
                         "CHECK-reject); successes don't count. Max attempts = target + max_fails.")
    ap.add_argument("--checker", choices=["manual", "sonnet", "none"], default="manual",
                    help="final write/regenerate gate. manual=dump pending pool for human/Claude "
                         "review; sonnet=inline gate via or-claude-sonnet; none=no gate")
    ap.add_argument("--checker_preset", default="or-claude-sonnet")
    ap.add_argument("--secret-type", default="",
                    help="enable the TYPE-aware gate (e.g. lying): keep only secrets suited to that "
                         "concealment type, via prompts/topic_judge_<type>.md (overrides --checker)")
    ap.add_argument("--gate-preset", default="",
                    help="API model for the type gate (e.g. or-gpt-5); default reuses the gen engine")
    ap.add_argument("--kept-out", default="",
                    help="also write kept topics in {kept:[...]} format for spec_build "
                         "(default benchmark_pool/topics_<type>.json when --secret-type is set)")
    ap.add_argument("--out", default="benchmark_pool/step1_pending.json")
    ap.add_argument("--seed_accepted", default=None,
                    help="optional topics json to seed the AVOID/dedup list (cross-run)")
    args = ap.parse_args()

    print(f"Loading corpus…")
    emails = load_emails()
    retriever = HybridRetriever([e.index_text for e in emails])
    print(f"  {len(emails)} emails indexed (BM25)")

    where = f"gpus={os.environ['CUDA_VISIBLE_DEVICES']}, tp={args.tp}" if args.engine == "vllm" else "API"
    print(f"Loading generator {args.engine}:{args.preset} ({where})…")
    engine = build_engine(args.engine, args.preset, tp=args.tp,
                          seed=args.seed, gpu_mem=args.gpu_mem)

    checker = None
    if args.secret_type:
        from src.grounding.check import TypeChecker
        gate_engine = (build_engine("api", args.gate_preset) if args.gate_preset else engine)
        checker = TypeChecker(args.secret_type, gate_engine)
        print(f"  CHECK gate: {args.secret_type} type-judge on "
              f"{args.gate_preset or (args.engine + ':' + args.preset)}")
    elif args.checker == "sonnet":
        from src.grounding.check import SonnetChecker
        print(f"  CHECK gate: {args.checker_preset} (inline)")
        checker = SonnetChecker(args.checker_preset)
    elif args.checker == "manual":
        print("  CHECK gate: manual — grounded candidates dumped as PENDING for review")

    accepted: list[dict] = []
    if args.seed_accepted and Path(args.seed_accepted).exists():
        seed = json.loads(Path(args.seed_accepted).read_text())
        accepted = [t for t in (seed.get("topics") if isinstance(seed, dict) else seed)]
        print(f"  seeded AVOID list with {len(accepted)} existing topics")

    discarded: list[dict] = []
    print(f"\n=== WORK ({args.n_work}) ===")
    used_anchors: set = set()          # shared so no anchor backs two topics, across categories
    work = run_category(engine, retriever, emails, "work", args.n_work,
                        accepted, discarded, args.max_fails, checker, used_anchors, args.secret_type)
    print(f"\n=== CASUAL ({args.n_casual}) ===")
    casual = run_category(engine, retriever, emails, "casual", args.n_casual,
                          accepted, discarded, args.max_fails, checker, used_anchors, args.secret_type)

    kept = work + casual

    # spec_build-ready output: {kept:[{id, topic, anchor, anchor_full_body}]} — same shape as
    # plot_generation.json, so `spec_build --plots <this>` runs STAGE 1 [2] + STAGE 2 on it.
    if args.secret_type:
        kept_entries = []
        for i, p in enumerate(kept, 1):
            tid = f"T{i:02d}"
            t = p["topic"]
            kept_entries.append({
                "id": tid, "category": t.get("category", "work"), "secret_type": args.secret_type,
                "topic": {"id": tid, "name": t.get("name", ""), "secret": t.get("secret", ""),
                          "true_fact": t.get("true_fact", ""), "false_belief": t.get("false_belief", "")},
                "anchor": p.get("anchor"), "anchor_full_body": p.get("anchor_full_body", ""),
            })
        kept_out = args.kept_out or f"benchmark_pool/topics_{args.secret_type}.json"
        Path(kept_out).write_text(json.dumps(
            {"_about": f"secret-first {args.secret_type}-typed topics (gate=topic_judge_{args.secret_type}); "
                       f"feed to spec_build --plots {kept_out}", "kept": kept_entries},
            indent=2, ensure_ascii=False))
        print(f"  kept-format -> {kept_out}  ({len(kept_entries)} topics; feed to spec_build --plots)")

    checker_id = args.checker_preset if args.checker == "sonnet" else args.checker
    out = {
        "_about": f"Step-1 written topics. gen/HyDE/fit-judge/specialize={args.engine}:{args.preset}; "
                  f"retrieval=BM25/RRF; CHECK={checker_id}.",
        "model": args.preset,
        "checker": args.checker,
        "config": {"tp": args.tp, "seed": args.seed, "n_work": args.n_work,
                   "n_casual": args.n_casual},
        "summary": {"kept": len(kept), "work": len(work), "casual": len(casual),
                    "discarded": len(discarded),
                    "discard_reasons": {s: sum(1 for d in discarded if d["status"] == s)
                                        for s in {d["status"] for d in discarded}}},
        "candidates": kept,
        "discarded": discarded,
    }
    Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False))

    # readable: only the written (passed) topics — no judge process, no failures
    readable = Path(args.out).with_suffix(".txt")
    lines = [f"Step 1 — {len(kept)} topics written", ""]
    for i, p in enumerate(kept, 1):
        t = p["topic"]
        a = p.get("anchor") or {}
        lines += [
            f"T{i:02d}  {t.get('name', '')}   [{t.get('category', 'work')}]",
            f"  secret      : {t.get('secret', '')}",
            f"  true_fact   : {t.get('true_fact', '')}",
            f"  false_belief: {t.get('false_belief', '')}",
            f"  anchor      : {a.get('date', '')[:10]}  {a.get('from', '')}  \"{a.get('subject', '')}\"",
            "",
        ]
    readable.write_text("\n".join(lines))
    print(f"\n=== {len(kept)} kept ({len(work)} work / {len(casual)} casual), "
          f"{len(discarded)} discarded -> {args.out}  |  readable -> {readable} ===")


if __name__ == "__main__":
    main()
