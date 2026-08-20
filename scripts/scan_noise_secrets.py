#!/usr/bin/env python3
"""Scan every corpus thread with a local grounded prober -> the threads that appear to carry a real
secret about a person, so they can be pulled from the noise pool.

We anonymize first (so the prober cannot recite a known Enron scandal) and require GROUNDING: the line
the prober quotes must actually occur in the thread, which separates real finds from confabulation.

  CUDA_VISIBLE_DEVICES=4,5 uv run python scripts/scan_noise_secrets.py --tp 2
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, "scripts")
sys.path.insert(0, ".")
from src.models.engine_factory import build_engine                           # noqa: E402
from src.agent.anonymize import build_subs, anon_text                        # noqa: E402

PROBER = Path("prompts/noise_prober.md")


def first_json(out: str):
    i = out.find("{")
    while i != -1:
        depth = 0
        for j in range(i, len(out)):
            if out[j] == "{":
                depth += 1
            elif out[j] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(out[i:j + 1])
                    except Exception:
                        break
        i = out.find("{", i + 1)
    return None


def norm(s):
    return " ".join((s or "").split()).lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", default="gemma4-31b")
    ap.add_argument("--tp", type=int, default=2)
    ap.add_argument("--gpu_mem", type=float, default=0.9)
    ap.add_argument("--model-len", type=int, default=4096, help="small ctx -> the prober only needs ~1k tokens")
    ap.add_argument("--corpus", default="data/enron_10/threads.jsonl")
    ap.add_argument("--max-chars", type=int, default=2500)
    ap.add_argument("--out", default="results/validity/noise_secret_scan")
    args = ap.parse_args()

    corpus = [json.loads(l) for l in Path(args.corpus).read_text().splitlines() if l.strip()]
    subs = build_subs()
    tmpl = PROBER.read_text()
    prompts, texts = [], []
    for t in corpus:
        body = (t.get("subject", "") or "") + "\n" + "\n".join(m.get("body", "") or "" for m in t["messages"])
        body = anon_text(body, subs)[:args.max_chars]
        texts.append(body)
        prompts.append(tmpl.replace("<<THREAD>>", body))

    eng = build_engine("vllm", args.preset, tp=args.tp, gpu_mem=args.gpu_mem, max_model_len=args.model_len)
    outs = eng.generate(prompts, max_tokens=200, temperature=0.0)

    flagged = []
    for t, body, o in zip(corpus, texts, outs):
        j = first_json(o) or {}
        if j.get("secret"):
            q = norm(j.get("quote", ""))
            grounded = bool(q) and q[:60] in norm(body)          # quoted line must occur in the thread
            flagged.append({"thread_id": t["thread_id"], "n_msg": len(t["messages"]),
                            "fact": j.get("fact", ""), "quote": j.get("quote", ""), "grounded": grounded})

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "flagged.jsonl").write_text("\n".join(json.dumps(f, ensure_ascii=False) for f in flagged) + "\n")
    ng = sum(1 for f in flagged if f["grounded"])
    print(f"threads scanned: {len(corpus)}   flagged secret: {len(flagged)}   "
          f"grounded: {ng}   ungrounded(confab?): {len(flagged) - ng}")
    print(f"WROTE {outdir}/flagged.jsonl")


if __name__ == "__main__":
    main()
