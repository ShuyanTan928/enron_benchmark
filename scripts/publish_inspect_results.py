#!/usr/bin/env python3
"""Validate completed Inspect run directories and publish them as a GitHub Release."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from inspect_ai.log import read_eval_log


def _run(*args: str, capture: bool = False) -> str:
    result = subprocess.run(
        args,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
    )
    return result.stdout.strip() if capture else ""


def _rows_count(path: Path) -> int:
    with path.open(newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _metric_values(results: Any) -> dict[str, dict[str, float]]:
    if results is None:
        return {}
    return {
        score.name: {
            name: float(metric.value)
            for name, metric in score.metrics.items()
            if isinstance(metric.value, (int, float))
        }
        for score in results.scores
    }


def _usage_values(stats: Any) -> dict[str, dict[str, int | float | None]]:
    if stats is None:
        return {}
    fields = (
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "input_tokens_cache_write",
        "input_tokens_cache_read",
        "reasoning_tokens",
        "total_cost",
    )
    return {
        model: {field: getattr(usage, field, None) for field in fields}
        for model, usage in stats.model_usage.items()
    }


def validate_run(run_dir: Path, *, allow_partial: bool, expected_samples: int | None) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    rows_path = run_dir / "rows.csv"
    logs = sorted((run_dir / "logs").glob("*.eval"))
    if not run_dir.is_dir():
        raise ValueError(f"run directory does not exist: {run_dir}")
    if not rows_path.is_file():
        raise ValueError(f"missing rows.csv: {run_dir}")
    if len(logs) != 1:
        raise ValueError(f"expected exactly one .eval log in {run_dir / 'logs'}, found {len(logs)}")

    log = read_eval_log(logs[0], header_only=True)
    results = log.results
    total = int(results.total_samples) if results is not None else 0
    completed = int(results.completed_samples) if results is not None else 0
    row_count = _rows_count(rows_path)
    if expected_samples is not None and total != expected_samples:
        raise ValueError(f"{run_dir.name}: expected {expected_samples} samples, log declares {total}")
    if not allow_partial:
        if log.status != "success":
            raise ValueError(f"{run_dir.name}: log status is {log.status!r}, not 'success'")
        if not total or completed != total:
            raise ValueError(f"{run_dir.name}: only {completed}/{total} samples completed")
        if row_count != completed:
            raise ValueError(f"{run_dir.name}: rows.csv has {row_count} rows for {completed} completed samples")

    return {
        "name": run_dir.name,
        "path": str(run_dir),
        "status": log.status,
        "model": log.eval.model,
        "task": log.eval.task,
        "task_args": log.eval.task_args,
        "created": log.eval.created,
        "completed_at": log.stats.completed_at if log.stats is not None else None,
        "total_samples": total,
        "completed_samples": completed,
        "csv_rows": row_count,
        "scores": _metric_values(results),
        "model_usage": _usage_values(log.stats),
        "eval_log": logs[0].name,
    }


def _repo_from_remote() -> str:
    remote = _run("git", "remote", "get-url", "origin", capture=True)
    match = re.search(r"github\.com(?::|/)([^/]+/[^/]+?)(?:\.git)?$", remote)
    if not match:
        raise ValueError(f"cannot derive GitHub repository from origin: {remote}")
    return match.group(1)


def _release_notes(manifest: dict[str, Any]) -> str:
    lines = [
        f"Inspect AI result set `{manifest['tag']}`.",
        "",
        "| Model | Samples | Final | Secret match | Tokens |",
        "|---|---:|---:|---:|---:|",
    ]
    for run in manifest["runs"]:
        scores = run["scores"]
        final = scores.get("final", {}).get("mean")
        match = scores.get("secret_match", {}).get("mean")
        tokens = sum((usage.get("total_tokens") or 0) for usage in run["model_usage"].values())
        lines.append(
            f"| `{run['model']}` | {run['completed_samples']}/{run['total_samples']} | "
            f"{final if final is not None else '—'} | {match if match is not None else '—'} | {tokens:,} |"
        )
    lines.extend(
        [
            "",
            f"Benchmark commit: `{manifest['git_commit']}`",
            "",
            "Each `.tar.gz` asset contains the native Inspect `.eval` trajectory and legacy-compatible `rows.csv`.",
        ]
    )
    return "\n".join(lines) + "\n"


def publish(
    run_dirs: list[Path],
    *,
    tag: str,
    repo: str,
    title: str | None,
    allow_partial: bool,
    expected_samples: int | None,
    dry_run: bool,
) -> dict[str, Any]:
    runs = [
        validate_run(path, allow_partial=allow_partial, expected_samples=expected_samples)
        for path in run_dirs
    ]
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "tag": tag,
        "repository": repo,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _run("git", "rev-parse", "HEAD", capture=True),
        "runs": runs,
        "assets": [],
    }

    with tempfile.TemporaryDirectory(prefix="inspect-release-") as temp_text:
        temp = Path(temp_text)
        assets: list[Path] = []
        for source, run in zip(run_dirs, runs, strict=True):
            asset = temp / f"{run['name']}.tar.gz"
            with tarfile.open(asset, "w:gz") as archive:
                archive.add(source.resolve(), arcname=run["name"])
            assets.append(asset)
            manifest["assets"].append(
                {"name": asset.name, "bytes": asset.stat().st_size, "sha256": _sha256(asset)}
            )

        manifest_path = temp / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        notes_path = temp / "release-notes.md"
        notes_path.write_text(_release_notes(manifest))
        assets.extend([manifest_path])

        if dry_run:
            print(json.dumps(manifest, indent=2, sort_keys=True))
            return manifest

        release_exists = subprocess.run(
            ["gh", "release", "view", tag, "--repo", repo],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0
        if release_exists:
            _run("gh", "release", "upload", tag, *map(str, assets), "--clobber", "--repo", repo)
            _run("gh", "release", "edit", tag, "--notes-file", str(notes_path), "--repo", repo)
        else:
            _run(
                "gh",
                "release",
                "create",
                tag,
                *map(str, assets),
                "--repo",
                repo,
                "--title",
                title or tag,
                "--notes-file",
                str(notes_path),
            )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dirs", nargs="+", type=Path)
    parser.add_argument("--tag", required=True, help="GitHub release tag")
    parser.add_argument("--repo", help="owner/repository; defaults to git origin")
    parser.add_argument("--title", help="release title; defaults to the tag")
    parser.add_argument("--expected-samples", type=int, help="require this declared sample count")
    parser.add_argument("--allow-partial", action="store_true", help="permit interrupted or incomplete logs")
    parser.add_argument("--dry-run", action="store_true", help="validate and print the manifest without uploading")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = args.repo or _repo_from_remote()
    publish(
        args.run_dirs,
        tag=args.tag,
        repo=repo,
        title=args.title,
        allow_partial=args.allow_partial,
        expected_samples=args.expected_samples,
        dry_run=args.dry_run,
    )
    if not args.dry_run:
        print(f"Published https://github.com/{repo}/releases/tag/{args.tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
