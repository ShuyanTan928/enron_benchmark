#!/usr/bin/env python3
"""Run or export the native Inspect AI Enron agent evaluation."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def normalize_azure_environment() -> None:
    """Map legacy Azure variable names to Inspect names in this process only."""

    try:
        from dotenv import load_dotenv

        load_dotenv(override=False)
    except ImportError:
        pass

    aliases = {
        "AZUREAI_OPENAI_API_KEY": ("AZURE_OPENAI_API_KEY",),
        "AZUREAI_OPENAI_BASE_URL": ("AZURE_OPENAI_BASE_URL", "AZURE_OPENAI_ENDPOINT"),
        "AZUREAI_OPENAI_API_VERSION": ("AZURE_OPENAI_API_VERSION", "OPENAI_API_VERSION"),
    }
    for target, sources in aliases.items():
        if os.environ.get(target):
            continue
        for source in sources:
            if os.environ.get(source):
                os.environ[target] = os.environ[source]
                break


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", help="evaluated Inspect model, e.g. openai/azure/gpt-5.6-luna")
    parser.add_argument("--judge-model", help="explicit recovery judge model")
    parser.add_argument("--noise", type=int, default=200, help="number of Enron noise threads")
    parser.add_argument("--budget", type=int, default=25, help="maximum mailbox actions")
    parser.add_argument("--scan", dest="scan", action="store_true", default=True)
    parser.add_argument("--no-scan", dest="scan", action="store_false", help="allow a negative answer without full segment coverage")
    parser.add_argument("--rerank", type=int, default=40, help="BM25 rerank pool; 0 disables reranking")
    parser.add_argument("--rerank-show", type=int, default=8)
    parser.add_argument("--segment-size", type=int, default=50)
    parser.add_argument("--seed", type=int, default=20260624)
    parser.add_argument("--min-invest", type=int, default=-1, help="qualifying searches/reads; -1 means clue count")
    parser.add_argument("--anonymize", default="benchmark_pool/pseudonyms.json")
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--max-samples", type=int, default=1, help="Inspect sample concurrency")
    parser.add_argument("--limit", type=int, help="run only the first N samples")
    parser.add_argument("--sample-id", help="run a single deterministic sample id")
    parser.add_argument("--out", required=True, help="output directory containing logs/ and rows.csv")
    parser.add_argument("--export-only", action="store_true", help="regenerate rows.csv from existing logs")
    parser.add_argument("--display", choices=("full", "conversation", "rich", "plain", "log", "none"), default="plain")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out)
    log_dir = out_dir / "logs"
    csv_path = out_dir / "rows.csv"

    normalize_azure_environment()

    try:
        from src.inspect_eval.export import export_rows
    except ImportError as exc:
        raise SystemExit(
            "Inspect AI is not installed. Run `uv sync`, then retry this command."
        ) from exc

    if args.export_only:
        rows = export_rows(log_dir, csv_path)
        print(f"Exported {len(rows)} row(s) to {csv_path}")
        return 0

    if not args.model or not args.judge_model:
        raise SystemExit("--model and --judge-model are required unless --export-only is used")
    if args.noise < 0 or args.budget < 1 or args.rerank < 0:
        raise SystemExit("--noise/--rerank must be non-negative and --budget must be positive")

    from inspect_ai import eval
    from src.inspect_eval.task import enron_agent_eval

    out_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    task = enron_agent_eval(
        judge_model=args.judge_model,
        noise=args.noise,
        budget=args.budget,
        scan=args.scan,
        segment_size=args.segment_size,
        rerank_pool=args.rerank,
        rerank_show=args.rerank_show,
        seed=args.seed,
        min_investigate=args.min_invest,
        anonymize=args.anonymize,
    )
    logs = eval(
        task,
        model=args.model,
        log_dir=str(log_dir),
        log_format="eval",
        epochs=args.epochs,
        max_samples=args.max_samples,
        limit=args.limit,
        sample_id=args.sample_id,
        display=args.display,
    )
    rows = export_rows(log_dir, csv_path)
    failed = [log for log in logs if log.status != "success"]
    print(f"Wrote {len(rows)} row(s) to {csv_path}")
    print(f"Inspect logs: {log_dir}  (view with: inspect view --log-dir {log_dir})")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
