"""Gen-4 fused runner: one per-topic loop that does Step-1 grounding + Step-2 plot + judge.

For each attempt:
  gen abstract topic -> HyDE -> BM25/RRF retrieve -> fit-judge ranks anchors
  -> for the top-N anchors: build the Step-2 plot prompt (anchor = real carrier, free casting),
     generate the plot, judge it (check1-7). First anchor whose plot PASSES is kept.
  -> if no anchor's plot passes, the abstract topic is recorded (so it is avoided next time).

The judge IS the gate — there is no separate Step-1 CHECK. The anchor only supplies a real
carrier + era; the secret/plot is imagined freely on top of it. Decoupling topic from anchor
(top-N retry) keeps a good topic from being wasted on one bad retrieval.

Usage (gemma full run):
  CUDA_VISIBLE_DEVICES=0,1 uv run python scripts/plot_generate.py \
      --engine vllm --preset gemma4-31b --tp 2 --n_work 10 --max-fails 40
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _early_gpus(default="0,1"):
    gpus = default
    for i, a in enumerate(sys.argv):
        if a == "--gpus" and i + 1 < len(sys.argv):
            gpus = sys.argv[i + 1]
        elif a.startswith("--gpus="):
            gpus = a.split("=", 1)[1]
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", gpus)


_early_gpus()
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))         # for sibling script imports

from src.models.engine_factory import build_engine                 # noqa: E402
from src.grounding.corpus import load_emails                           # noqa: E402
from src.grounding.retrieval import HybridRetriever                    # noqa: E402
from src.grounding.pipeline import propose_grounding                   # noqa: E402
from plot_assemble import make_relabel, scrub_corp                # noqa: E402
from plot_iterate import extract_json, judge, all_pass, context_of, CRITERIA  # noqa: E402

TEMPLATE = (ROOT / "prompts/secret_plot_from_carrier.md").read_text()


def build_plot_prompt(topic: dict, anchor, relabel, team: str) -> str:
    """Fill secret_plot_from_carrier.md with the abstract secret + this anchor (relabeled,
    company-scrubbed) + the team roster — same shape plot_assemble.py produces."""
    topic_json = json.dumps(
        {"id": topic.get("id", "T??"), "name": topic["name"],
         "secret": topic["secret"], "either_or": topic["either_or"]},
        indent=2, ensure_ascii=False)
    to = ", ".join(relabel(x) for x in anchor.to_names[:4]) or "(internal)"
    anchor_block = (
        f'From: {relabel(anchor.from_name)}  →  To: {to}   ({anchor.date[:10]})\n'
        f'Subject: "{relabel(anchor.subject)}"\n\n{relabel(anchor.body[:1500])}'
    )
    out = (TEMPLATE.replace("<<TOPIC>>", topic_json)
                   .replace("<<ANCHOR>>", anchor_block)
                   .replace("<<RELATIONSHIPS>>", team)
                   .replace("<<TID>>", topic.get("id", "T??")))
    return scrub_corp(out)


def run_category(gen_engine, judge_engine, retriever, emails, category, target, max_fails,
                 max_anchor_tries, relabel, team, accepted, rejected, used_anchors, kept, discarded):
    fails = 0
    while len(kept) < target and fails < max_fails:
        p = propose_grounding(gen_engine, retriever, emails, category, accepted + rejected,
                              used_anchors=used_anchors)
        st = p["status"]
        topic = p.get("topic")
        name = (topic or {}).get("name", "?")
        if st != "grounded":
            fails += 1
            discarded.append({"status": st, "topic": topic})
            if topic:
                rejected.append(topic)
            print(f"  [{category} fail {fails}/{max_fails}] {st.upper():10} «{name}»")
            continue

        topic["id"] = f"T{len(kept) + 1:02d}"
        passed = None
        tried = []
        for anchor in p["anchors"][:max_anchor_tries]:
            prompt = build_plot_prompt(topic, anchor, relabel, team)
            raw = gen_engine.generate(prompt, max_tokens=3072, temperature=0.5)[0]
            cand = extract_json(raw)
            if cand is None:
                tried.append({"anchor_date": anchor.date[:10], "result": "parse_fail"})
                continue
            verdict, _ = judge(judge_engine, context_of(prompt), cand)
            ok = all_pass(verdict)
            summ = {c: (verdict.get(c) or {}).get("verdict") for c in CRITERIA} if verdict else None
            tried.append({"anchor_date": anchor.date[:10], "subject": anchor.subject[:45],
                          "result": "PASS" if ok else "fail", "summary": summ,
                          "candidate": cand, "verdict": verdict})
            if ok:
                passed = (anchor, cand, verdict)
                break

        if passed is None:
            fails += 1
            rejected.append(topic)
            discarded.append({"status": "plot_reject", "topic": topic, "tried": tried})
            print(f"  [{category} fail {fails}/{max_fails}] PLOT-REJECT «{name}»  "
                  f"(anchors tried: {len(tried)})")
            continue

        anchor, cand, verdict = passed
        kept.append({
            "id": topic["id"], "category": category, "topic": topic,
            "anchor": anchor.anchor_dict(), "anchor_full_body": anchor.body[:1500],
            "plot": cand, "judge": verdict,
        })
        accepted.append(topic)
        used_anchors.add(anchor.message_id)
        print(f"  [{category} {len(kept)}/{target}] OK  «{name}»  -> {anchor.date[:10]} "
              f'"{anchor.subject[:38]}"  (anchor #{len(tried)})')
    return kept


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen-engine", choices=["vllm", "api"], default="vllm")
    ap.add_argument("--gen-preset", default="gemma4-31b")
    ap.add_argument("--judge-engine", choices=["vllm", "api"], default=None,
                    help="default: same backend as --gen-engine")
    ap.add_argument("--judge-preset", default=None,
                    help="default: reuse the gen engine; cross-vendor wants a different judge")
    ap.add_argument("--gpus", default="0,1")
    ap.add_argument("--tp", type=int, default=2)
    ap.add_argument("--gpu_mem", type=float, default=0.9)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--n_work", type=int, default=10)
    ap.add_argument("--max-fails", type=int, default=40)
    ap.add_argument("--max-anchor-tries", type=int, default=2)
    ap.add_argument("--people", default="benchmark_pool/people.json")
    ap.add_argument("--out", default="benchmark_pool/plot_pending.json")
    args = ap.parse_args()

    print("Loading corpus…")
    emails = load_emails()
    retriever = HybridRetriever([e.index_text for e in emails])
    print(f"  {len(emails)} emails indexed (BM25)")

    people = json.loads(Path(args.people).read_text())
    P, AUTH = people["people"], people["authority"]
    relabel = make_relabel(P)
    team = "\n".join(["Team:"] + [f"- {p['label']} — {p['role']}" for p in P]
                     + ["", "Authority:"] + [f"- {e['from']} {e['rel']} {e['to']}" for e in AUTH])

    print(f"Loading gen {args.gen_engine}:{args.gen_preset} …")
    gen_engine = build_engine(args.gen_engine, args.gen_preset, tp=args.tp, seed=args.seed, gpu_mem=args.gpu_mem)
    je = args.judge_engine or args.gen_engine
    if args.judge_preset and (args.judge_preset != args.gen_preset or je != args.gen_engine):
        print(f"Loading judge {je}:{args.judge_preset} (independent) …")
        judge_engine = build_engine(je, args.judge_preset, tp=args.tp, seed=args.seed, gpu_mem=args.gpu_mem)
    else:
        print("judge: reusing gen engine")
        judge_engine = gen_engine

    accepted, rejected, discarded, kept = [], [], [], []
    used_anchors: set = set()
    print(f"\n=== WORK ({args.n_work}); max_fails={args.max_fails}, anchor_tries={args.max_anchor_tries} ===")
    run_category(gen_engine, judge_engine, retriever, emails, "work", args.n_work, args.max_fails,
                 args.max_anchor_tries, relabel, team, accepted, rejected, used_anchors,
                 kept, discarded)

    out = {
        "_about": f"Gen-4 fused (Step1 grounding + Step2 plot + judge). gen={args.gen_engine}:{args.gen_preset}; "
                  f"judge={je}:{args.judge_preset or args.gen_preset}; retrieval=BM25/RRF; no specialize; "
                  f"anchor=carrier+era; free casting.",
        "config": {"gen_preset": args.gen_preset, "judge_preset": args.judge_preset or args.gen_preset,
                   "n_work": args.n_work, "max_fails": args.max_fails,
                   "max_anchor_tries": args.max_anchor_tries, "seed": args.seed},
        "summary": {"kept": len(kept), "discarded": len(discarded),
                    "discard_reasons": {s: sum(1 for d in discarded if d["status"] == s)
                                        for s in {d["status"] for d in discarded}}},
        "kept": kept,
        "discarded": discarded,
    }
    Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False))

    readable = Path(args.out).with_suffix(".txt")
    lines = [f"Gen-4 — {len(kept)} topics kept", ""]
    for k in kept:
        t, a, pl = k["topic"], k["anchor"], k["plot"]
        lines += [
            f"{k['id']}  {t.get('name', '')}",
            f"  secret   : {t.get('secret', '')}",
            f"  either_or: {t.get('either_or', '')}",
            f"  anchor   : {a.get('date', '')[:10]}  {a.get('from', '')}  \"{a.get('subject', '')}\"",
            f"  actor    : {pl.get('actor', '')}",
            f"  victim   : {pl.get('victim', '')}",
            f"  plot     : {pl.get('plot', '')[:500]}",
            "",
        ]
    readable.write_text("\n".join(lines))
    print(f"\n=== {len(kept)} kept, {len(discarded)} discarded -> {args.out}  |  readable -> {readable} ===")


if __name__ == "__main__":
    main()
