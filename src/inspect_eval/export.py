"""Export native Inspect logs to the legacy rows.csv schema."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable

from inspect_ai.log import EvalLog, list_eval_logs, read_eval_log

from src.inspect_eval.core import DEFAULT_TOPICS, LEGACY_CSV_FIELDS


CSV_FIELDS = list(LEGACY_CSV_FIELDS)

CONFIG_ORDER = {name: pos for pos, name in enumerate(("com_n2", "com_n3", "pal_n2", "pal_n3"))}
TOPIC_ORDER = {name: pos for pos, name in enumerate(DEFAULT_TOPICS)}


def _stored(sample: Any, key: str, default: Any = "") -> Any:
    return sample.store.get(f"EnronStore:{key}", default)


def _score(sample: Any) -> Any | None:
    if not sample.scores:
        return None
    for name, value in sample.scores.items():
        if name.split("/")[-1] == "enron_recovery_scorer":
            return value
    return next(iter(sample.scores.values()))


def _sample_row(sample: Any) -> dict[str, Any]:
    score = _score(sample)
    values = score.value if score is not None and isinstance(score.value, dict) else {}
    details = score.metadata if score is not None and isinstance(score.metadata, dict) else {}
    metadata = sample.metadata or {}
    secret = details.get("secret", score.answer if score is not None else "") or ""
    return {
        "config": metadata.get("config", _stored(sample, "config")),
        "topic": metadata.get("topic", _stored(sample, "topic")),
        "control": 0,
        "rep": metadata.get("rep", 0),
        "budget": metadata.get("budget", details.get("budget", _stored(sample, "budget"))),
        "found": values.get("found", ""),
        "secret_match": values.get("secret_match", ""),
        "ev_recall": values.get("ev_recall", ""),
        "ev_precision": values.get("ev_precision", ""),
        "final": values.get("final", ""),
        "false_positive": "",
        "n_tool_calls": details.get("n_tool_calls", ""),
        "n_search": details.get("n_search", ""),
        "n_read": details.get("n_read", ""),
        "n_emails_opened": details.get("n_emails_opened", ""),
        "n_redundant_reads": details.get("n_redundant_reads", ""),
        "n_clues_total": details.get("n_clues_total", metadata.get("n_clues", "")),
        "n_clues_read": details.get("n_clues_read", ""),
        "clue_recall": values.get("clue_recall", details.get("clue_recall", "")),
        "turns": details.get("turns", _stored(sample, "turns")),
        "budget_hit": details.get("budget_hit", int(bool(_stored(sample, "budget_hit", False)))),
        "certified": "",
        "latency_s": round(float(sample.total_time), 3) if sample.total_time is not None else "",
        "tester_chars": details.get("tester_chars", _stored(sample, "tester_chars")),
        "secret": str(secret)[:400],
    }


def rows_from_logs(logs: Iterable[EvalLog]) -> list[dict[str, Any]]:
    """Collect the latest occurrence of each sample/epoch from one or more logs."""

    latest: dict[tuple[str, int], dict[str, Any]] = {}
    for log in logs:
        for sample in log.samples or []:
            latest[(str(sample.id), int(sample.epoch))] = _sample_row(sample)
    rows = list(latest.values())
    rows.sort(
        key=lambda row: (
            CONFIG_ORDER.get(str(row["config"]), 999),
            TOPIC_ORDER.get(str(row["topic"]), 999),
            int(row["rep"] or 0),
        )
    )
    return rows


def export_rows(log_dir: str | Path, csv_path: str | Path) -> list[dict[str, Any]]:
    """Read all .eval logs and write a plotting-compatible CSV."""

    infos = list_eval_logs(str(log_dir), formats=["eval"], descending=False)
    if not infos:
        raise FileNotFoundError(f"No Inspect .eval logs found under {log_dir}")
    logs = [read_eval_log(info.name) for info in infos]
    rows = rows_from_logs(logs)
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return rows
