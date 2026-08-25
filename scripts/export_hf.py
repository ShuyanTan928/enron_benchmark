#!/usr/bin/env python3
"""Export a benchmark directory to a Hugging Face `datasets`-loadable form (JSONL + a dataset card).

This produces a self-contained folder you can `datasets.load_dataset("json", data_files=...)` on, or
push with `huggingface-cli upload`. Only the PROCESSED, pseudonymized derivative is exported; the raw
Enron corpus is never redistributed (users obtain it from CMU — see DATA_CARD.md).

Usage:
  uv run python scripts/export_hf.py --in-dir benchmark_v2 --out-dir dist/hf
Then, to publish (requires `huggingface_hub` and a logged-in token):
  huggingface-cli upload <org>/<name> dist/hf . --repo-type dataset
"""
from __future__ import annotations
import argparse
import glob
import json
from pathlib import Path


def export(in_dir: str, out_dir: str) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    with (out / "cases.jsonl").open("w") as fh:
        for path in sorted(glob.glob(str(Path(in_dir) / "emails_*.jsonl"))):
            cfg = Path(path).stem.replace("emails_", "")
            for line in Path(path).read_text().splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                if r.get("status") != "KEPT":
                    continue
                rec = {
                    "id": f"{cfg}-{r['topic_id']}",
                    "config": cfg,
                    "topic_id": r["topic_id"],
                    "n": int(r.get("n") or len(r.get("clues", []))),
                    "secret_type": r.get("secret_type", ""),
                    "register": "work" if r["topic_id"].startswith("W") else "casual",
                    "secret": (r.get("answer") or {}).get("secret", ""),
                    "actor": (r.get("answer") or {}).get("actor", ""),
                    "victim": (r.get("answer") or {}).get("victim", ""),
                    "clues": r.get("clues", []),
                }
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n += 1
    # A minimal HF dataset card front-matter; extend from DATA_CARD.md before publishing.
    (out / "README.md").write_text(
        "---\n"
        "license: cc-by-4.0\n"
        "task_categories:\n  - other\n"
        "tags:\n  - privacy\n  - llm-agents\n  - benchmark\n"
        "---\n\n"
        "# Enron Distributed-Clue Deception Benchmark\n\n"
        f"{n} cases. See DATA_CARD.md in the source repository for construction, privacy handling, "
        "and intended use. The raw Enron corpus is not redistributed here; obtain it from "
        "https://www.cs.cmu.edu/~enron/ .\n"
    )
    print(f"exported {n} cases -> {out}/cases.jsonl  (+ dataset card)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-dir", default="benchmark_v2")
    ap.add_argument("--out-dir", default="dist/hf")
    args = ap.parse_args()
    export(args.in_dir, args.out_dir)


if __name__ == "__main__":
    main()
