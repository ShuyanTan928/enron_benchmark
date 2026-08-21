import csv
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import publish_inspect_results as publish


def _run_dir(tmp_path: Path, rows: int = 2) -> Path:
    run = tmp_path / "model_n200"
    (run / "logs").mkdir(parents=True)
    (run / "logs" / "result.eval").write_bytes(b"placeholder")
    with (run / "rows.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["found", "final"])
        writer.writeheader()
        for _ in range(rows):
            writer.writerow({"found": 1, "final": 1})
    return run


def _log(*, status="success", total=2, completed=2):
    metric = SimpleNamespace(value=1.0)
    score = SimpleNamespace(name="final", metrics={"mean": metric})
    usage = SimpleNamespace(
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
        input_tokens_cache_write=None,
        input_tokens_cache_read=None,
        reasoning_tokens=2,
        total_cost=None,
    )
    return SimpleNamespace(
        status=status,
        eval=SimpleNamespace(
            model="openai/test",
            task="enron_agent_eval",
            task_args={"noise": 200},
            created="2026-08-21T00:00:00Z",
        ),
        stats=SimpleNamespace(completed_at="2026-08-21T00:01:00Z", model_usage={"openai/test": usage}),
        results=SimpleNamespace(total_samples=total, completed_samples=completed, scores=[score]),
    )


def test_validate_completed_run(monkeypatch, tmp_path):
    run = _run_dir(tmp_path)
    monkeypatch.setattr(publish, "read_eval_log", lambda *_args, **_kwargs: _log())

    result = publish.validate_run(run, allow_partial=False, expected_samples=2)

    assert result["status"] == "success"
    assert result["csv_rows"] == 2
    assert result["scores"]["final"]["mean"] == 1.0
    assert result["model_usage"]["openai/test"]["total_tokens"] == 15


def test_validate_rejects_partial_and_row_mismatch(monkeypatch, tmp_path):
    run = _run_dir(tmp_path, rows=1)
    monkeypatch.setattr(
        publish,
        "read_eval_log",
        lambda *_args, **_kwargs: _log(status="cancelled", total=2, completed=1),
    )

    with pytest.raises(ValueError, match="status"):
        publish.validate_run(run, allow_partial=False, expected_samples=2)

    result = publish.validate_run(run, allow_partial=True, expected_samples=2)
    assert result["completed_samples"] == 1


def test_repo_from_ssh_remote(monkeypatch):
    monkeypatch.setattr(publish, "_run", lambda *_args, **_kwargs: "git@github.com:owner/repo.git")
    assert publish._repo_from_remote() == "owner/repo"
