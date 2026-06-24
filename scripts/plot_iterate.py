#!/usr/bin/env python3
"""Step 2 with an iteration gate: generate -> judge (rubric A-G) -> regenerate on fail.

Generation and judging run on a local vLLM model (one engine, reused by default); pass
--judge-preset to use a different / stronger judge. The judge applies prompts/secret_plot_judge.md
(criteria A-G; anonymization is OUT of scope). A candidate is kept only when every criterion is
PASS; otherwise the failing reasons + fix are fed back and the topic is regenerated, up to
--max-iters. Kept candidates are written to --out (same schema as step2_lean.jsonl); a full
per-topic attempt log goes to <out>.attempts.json.

Usage:
  CUDA_VISIBLE_DEVICES=4,5,6,7 uv run python scripts/plot_iterate.py \
      --gen-preset gemma4-31b --tp 4 --max-iters 3 --out benchmark_pool/step2_iter.jsonl
  # one topic:
  CUDA_VISIBLE_DEVICES=4,5,6,7 uv run python scripts/plot_iterate.py --topic T07
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

JUDGE_TMPL = Path("prompts/secret_plot_judge.md")
CRITERIA = ["check1_grounded", "check2_binary", "check3_casting", "check4_positive_act",
            "check5_material", "check6_consistent", "check7_localized"]


def extract_json(text: str) -> dict | None:
    t = text.strip()
    t = re.sub(r"^```(?:json)?", "", t).strip()
    t = re.sub(r"```$", "", t).strip()
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        return json.loads(t[start:end + 1])
    except json.JSONDecodeError:
        for m in reversed(list(re.finditer(r"\{.*?\}", t, re.DOTALL))):
            if "verdict" in m.group(0) or "topic_id" in m.group(0):
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    continue
        return None


def context_of(assembled: str) -> str:
    """Slice SECRET + ANCHOR + TEAM out of an assembled generation prompt."""
    i = assembled.find("## SECRET")
    j = assembled.find("## Write the PLOT")
    return assembled[i:j].strip() if (i != -1 and j != -1) else assembled


def judge(engine, context: str, candidate: dict) -> tuple[dict | None, str]:
    prompt = (JUDGE_TMPL.read_text()
              .replace("<<CONTEXT>>", context)
              .replace("<<CANDIDATE>>", json.dumps(candidate, indent=2, ensure_ascii=False)))
    raw = engine.generate(prompt, max_tokens=1400, temperature=0.0)[0]
    return extract_json(raw), raw


def all_pass(v: dict | None) -> bool:
    return v is not None and all(
        (v.get(c) or {}).get("verdict", "").upper() == "PASS" for c in CRITERIA)


def feedback_from(v: dict) -> str:
    lines = []
    for c in CRITERIA:
        d = v.get(c) or {}
        if d.get("verdict", "").upper() != "PASS":
            lines.append(f"- {c} [{d.get('verdict')}]: {d.get('reason', '')}")
    fix = v.get("fix", "")
    return ("A prior attempt failed review:\n" + "\n".join(lines)
            + (f"\nFIX: {fix}" if fix else "")
            + "\nReturn ONE corrected JSON object in the same schema, nothing else.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--indir", default="prompts/plot")
    ap.add_argument("--gen-engine", choices=["vllm", "api"], default="vllm")
    ap.add_argument("--gen-preset", default="gemma4-31b")
    ap.add_argument("--judge-engine", choices=["vllm", "api"], default=None,
                    help="default: same backend as --gen-engine")
    ap.add_argument("--judge-preset", default=None,
                    help="default: reuse the gen engine (separation of duties wants a different model)")
    ap.add_argument("--tp", type=int, default=4)
    ap.add_argument("--max-iters", type=int, default=3)
    ap.add_argument("--gen-temp", type=float, default=0.5)
    ap.add_argument("--topic", default="all")
    ap.add_argument("--out", default="benchmark_pool/step2_iter.jsonl")
    args = ap.parse_args()

    files = sorted(Path(args.indir).glob("T*.txt"))
    if args.topic != "all":
        files = [f for f in files if f.stem == args.topic]
    print(f"{len(files)} topic(s): {', '.join(f.stem for f in files)}")

    from src.models.engine_factory import build_engine
    print(f"loading gen {args.gen_engine}:{args.gen_preset} (tp={args.tp}) ...")
    gen = build_engine(args.gen_engine, args.gen_preset, tp=args.tp)
    judge_engine = args.judge_engine or args.gen_engine
    if args.judge_preset and (args.judge_preset != args.gen_preset or judge_engine != args.gen_engine):
        print(f"loading judge {judge_engine}:{args.judge_preset} (independent) ...")
        jud = build_engine(judge_engine, args.judge_preset, tp=args.tp)
    else:
        print("judge: reusing gen engine")
        jud = gen

    kept, logs = [], []
    for f in files:
        tid, base = f.stem, f.read_text()
        ctx = context_of(base)
        prompt, accepted, attempts = base, None, []
        for it in range(1, args.max_iters + 1):
            raw = gen.generate(prompt, max_tokens=3072, temperature=args.gen_temp)[0]
            cand = extract_json(raw)
            if cand is None:
                attempts.append({"iter": it, "result": "parse_fail"})
                prompt = base + "\n\n## CORRECTION REQUIRED\nYour previous output was not valid JSON. Output ONLY the JSON object."
                print(f"  {tid} iter{it}: parse_fail")
                continue
            v, _ = judge(jud, ctx, cand)
            ok = all_pass(v)
            summ = {c: (v.get(c) or {}).get("verdict") for c in CRITERIA} if v else None
            attempts.append({"iter": it, "result": "PASS" if ok else "fail",
                             "verdicts": summ, "candidate": cand, "judge": v})
            print(f"  {tid} iter{it}: {'PASS' if ok else 'fail'}  {summ}")
            if ok:
                accepted = cand
                break
            prompt = base if v is None else base + "\n\n## CORRECTION REQUIRED\n" + feedback_from(v)

        if accepted is not None:
            kept.append(accepted)
        logs.append({"topic_id": tid, "status": "PASS" if accepted else "DROP",
                     "iters": len(attempts), "attempts": attempts})
        print(f"  -> {tid} {'KEPT' if accepted else 'DROPPED'} after {len(attempts)} iter(s)\n")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as fh:
        for k in kept:
            fh.write(json.dumps(k, ensure_ascii=False) + "\n")
    Path(str(out) + ".attempts.json").write_text(json.dumps(logs, indent=2, ensure_ascii=False))
    print(f"WROTE {out}  ({len(kept)}/{len(files)} kept)  |  log -> {out}.attempts.json")


if __name__ == "__main__":
    main()
