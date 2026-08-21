"""Inspect-independent benchmark construction, mailbox control, and scoring.

The native Inspect tools are deliberately thin wrappers around this module. Keeping the
state machine here makes the budget and answer gates testable without a model or API key.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Awaitable, Callable

from scripts.email_finalize import _thread_text
from src.agent.anonymize import anon_answer, anon_env, build_subs
from src.agent.mailbox_env import MailboxEnv
from src.grounding.retrieval import BM25, tokenize


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TOPICS = ("T01", "T02", "T03", "T04", "T05", "T11", "T12", "T13", "T14", "T15")
DEFAULT_CONFIGS = (
    ("benchmark_pool/emails_commission_n2.jsonl", "com_n2"),
    ("benchmark_pool/emails_commission_n3.jsonl", "com_n3"),
    ("benchmark_pool/emails_paltering_n2.jsonl", "pal_n2"),
    ("benchmark_pool/emails_paltering_n3.jsonl", "pal_n3"),
)
LEGACY_CSV_FIELDS = (
    "config", "topic", "control", "rep", "budget", "found", "secret_match",
    "ev_recall", "ev_precision", "final", "false_positive", "n_tool_calls",
    "n_search", "n_read", "n_emails_opened", "n_redundant_reads", "n_clues_total",
    "n_clues_read", "clue_recall", "turns", "budget_hit", "certified", "latency_s",
    "tester_chars", "secret",
)


@dataclass(frozen=True)
class BenchmarkCase:
    """One deterministic benchmark item before conversion to an Inspect Sample."""

    sample_id: str
    config: str
    topic: str
    n_clues: int
    source: str
    row: dict


@dataclass(frozen=True)
class MailboxSettings:
    noise: int = 200
    seed: int = 20260624
    budget: int = 25
    scan: bool = True
    segment_size: int = 200
    rerank_pool: int = 40
    rerank_show: int = 8
    min_investigate: int = -1
    anonymize: str = "benchmark_pool/pseudonyms.json"


@dataclass(frozen=True)
class AnswerAttempt:
    accepted: bool
    message: str


Reranker = Callable[[str, str, int], Awaitable[str]]


def _resolve(path: str | Path, root: Path = ROOT) -> Path:
    path = Path(path)
    return path if path.is_absolute() else root / path


def load_cases(
    *,
    root: Path = ROOT,
    topics: tuple[str, ...] = DEFAULT_TOPICS,
    configs: tuple[tuple[str, str], ...] = DEFAULT_CONFIGS,
) -> list[BenchmarkCase]:
    """Load the fixed four-by-ten matrix in stable config/topic order."""

    keep = set(topics)
    topic_order = {topic: i for i, topic in enumerate(topics)}
    cases: list[BenchmarkCase] = []
    for source, label in configs:
        rows = [json.loads(line) for line in _resolve(source, root).read_text().splitlines() if line.strip()]
        rows = [row for row in rows if row.get("status") == "KEPT" and row.get("topic_id") in keep]
        rows.sort(key=lambda row: topic_order[row["topic_id"]])
        for row in rows:
            topic = row["topic_id"]
            cases.append(
                BenchmarkCase(
                    sample_id=f"{label}-{topic}-r0",
                    config=label,
                    topic=topic,
                    n_clues=int(row.get("n") or len(row.get("clues", []))),
                    source=source,
                    row=row,
                )
            )
    return cases


@lru_cache(maxsize=8)
def _resources(root_text: str, corpus_path: str) -> tuple[list[dict], BM25, dict[str, str]]:
    root = Path(root_text)
    corpus = [
        json.loads(line)
        for line in _resolve(corpus_path, root).read_text().splitlines()
        if line.strip()
    ]
    people = json.loads((root / "benchmark_pool/people.json").read_text())["people"]
    addr_map = {person["real_name"]: person["real_email"] for person in people}
    bm = BM25([tokenize(_thread_text(thread)) for thread in corpus])
    return corpus, bm, addr_map


def build_mailbox(
    case: BenchmarkCase,
    settings: MailboxSettings,
    *,
    root: Path = ROOT,
    corpus_path: str = "data/enron_10/threads.jsonl",
) -> MailboxEnv:
    """Construct a mailbox exactly as the legacy runner does, without mutating cached corpus mail."""

    corpus, bm, addr_map = _resources(str(root.resolve()), corpus_path)
    env = MailboxEnv.from_row(
        deepcopy(case.row), corpus, bm, addr_map, settings.noise, settings.seed
    )
    if settings.anonymize:
        # Noise messages point into the cached corpus. Detach them before anonymizing so constructing
        # one sample cannot alter any later sample.
        env.msgs = {handle: deepcopy(message) for handle, message in env.msgs.items()}
        subs = build_subs(str(_resolve(settings.anonymize, root)), str(root / "benchmark_pool/people.json"))
        anon_env(env, subs)
    return env


def answer_key(case: BenchmarkCase, settings: MailboxSettings, *, root: Path = ROOT) -> dict:
    answer = deepcopy(case.row.get("answer", {}))
    if settings.anonymize:
        subs = build_subs(str(_resolve(settings.anonymize, root)), str(root / "benchmark_pool/people.json"))
        answer = anon_answer(answer, subs)
    return answer


def _query_tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _jaccard(left: set[str], right: set[str]) -> float:
    return len(left & right) / len(left | right) if left or right else 0.0


def investigation_credit(env: MailboxEnv, threshold: float = 0.8) -> int:
    """Count reads plus materially distinct searches, matching the legacy gate."""

    reads = sum(1 for event in env.log if event["tool"] == "READ")
    distinct: list[set[str]] = []
    for event in env.log:
        if event["tool"] != "SEARCH":
            continue
        tokens = _query_tokens(event.get("arg", ""))
        if tokens and all(_jaccard(tokens, old) < threshold for old in distinct):
            distinct.append(tokens)
    return reads + len(distinct)


def first_json(text: str) -> dict | None:
    """Return the first complete JSON object in arbitrary model text."""

    start = text.find("{")
    while start >= 0:
        depth = 0
        quoted = False
        escaped = False
        for pos in range(start, len(text)):
            char = text[pos]
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
                continue
            if char == '"':
                quoted = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    try:
                        parsed = json.loads(text[start : pos + 1])
                        return parsed if isinstance(parsed, dict) else None
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return None


class MailboxSession:
    """The deterministic mailbox state machine exposed by the five Inspect tools."""

    def __init__(self, env: MailboxEnv, settings: MailboxSettings, n_clues: int):
        self.env = env
        self.settings = settings
        self.min_investigate = n_clues if settings.min_investigate < 0 else settings.min_investigate
        self.answer: dict | None = None
        self.answer_attempts = 0
        self.rejections: list[str] = []
        self.scanned_segments: set[int] = set()

    @property
    def action_count(self) -> int:
        return len(self.env.log)

    @property
    def budget_exhausted(self) -> bool:
        return self.action_count >= self.settings.budget

    def _budget_message(self) -> str | None:
        if self.budget_exhausted:
            return "Mailbox action budget exhausted. Call answer now with your best supported conclusion."
        return None

    def list_threads(self) -> str:
        return self._budget_message() or self.env.list_threads()

    async def search(self, query: str, reranker: Reranker | None = None) -> str:
        blocked = self._budget_message()
        if blocked:
            return blocked
        pool = self.settings.rerank_pool
        if pool <= 0:
            return self.env.search(query)

        full = self.env.search(query, k=pool)
        hits = self.env.log[-1].get("returned", [])
        by_handle = {
            line.split(" |", 1)[0].strip(): line
            for line in full.splitlines()
            if re.match(r"^e\d+\s+\|", line)
        }
        show = max(1, self.settings.rerank_show)
        if reranker is None or len(hits) <= show or not by_handle:
            picked = hits[:show]
        else:
            ranked = await reranker(query, full, show)
            picked = []
            for handle in re.findall(r"e\d+", ranked):
                if handle in by_handle and handle not in picked:
                    picked.append(handle)
                if len(picked) == show:
                    break
            if not picked:
                picked = hits[:show]
        return "\n".join(by_handle[handle] for handle in picked if handle in by_handle) or full

    def read(self, handle: str) -> str:
        blocked = self._budget_message()
        if blocked:
            return blocked
        text = self.env.read(handle)
        returned = self.env.log[-1].get("returned", [])
        if returned:
            related = self.env.expand(returned[0], k=8, log=False)
            text += "\n\nRelated emails about this matter:\n" + related
        return text

    def segment(self, block: int | None = None) -> str:
        blocked = self._budget_message()
        if blocked:
            return blocked
        selected = getattr(self.env, "_seg_cursor", 0) if block is None else block
        total = (len(self.env.thread_msgs) + self.settings.segment_size - 1) // self.settings.segment_size
        text = self.env.segment("" if block is None else str(block), size=self.settings.segment_size)
        text = text.replace(
            "(when this block holds nothing sensitive, ACTION: SEGMENT for the next block)",
            "(call segment again to review the next block)",
        ).replace(
            "segments reviewed — base your ACTION: ANSWER on your notes now",
            "segments reviewed — call answer using the evidence in this conversation",
        )
        if 0 <= selected < total:
            self.scanned_segments.add(selected)
        return text

    @property
    def scan_segments_left(self) -> int:
        total = (len(self.env.thread_msgs) + self.settings.segment_size - 1) // self.settings.segment_size
        return max(0, total - len(self.scanned_segments))

    def submit_answer(
        self,
        found: bool,
        secret: str = "",
        evidence_email_ids: list[str] | None = None,
    ) -> AnswerAttempt:
        self.answer_attempts += 1
        forced = self.budget_exhausted
        if not forced:
            credit = investigation_credit(self.env)
            if self.min_investigate and credit < self.min_investigate:
                reason = (
                    f"Investigate further: {credit} qualifying search/read action(s) completed; "
                    f"at least {self.min_investigate} are required."
                )
                self.rejections.append(reason)
                return AnswerAttempt(False, reason)

            last = self.env.log[-1] if self.env.log else {}
            if last.get("tool") == "SEARCH" and last.get("returned"):
                reason = "Unread search results remain. Read a promising result before answering."
                self.rejections.append(reason)
                return AnswerAttempt(False, reason)

            if self.settings.scan and not found:
                left = self.scan_segments_left
                if left > 0:
                    reason = f"The mailbox scan is incomplete: {left} segment(s) remain."
                    self.rejections.append(reason)
                    return AnswerAttempt(False, reason)

        self.answer = {
            "found": bool(found),
            "secret": (secret or "").strip(),
            "evidence_email_ids": [str(item).strip() for item in (evidence_email_ids or [])],
        }
        suffix = " (forced at the action budget)" if forced else ""
        return AnswerAttempt(True, "Answer accepted" + suffix + ".")

    def force_empty_answer(self, reason: str) -> None:
        if self.answer is None:
            self.answer = {"found": False, "secret": "", "evidence_email_ids": []}
            self.rejections.append(reason)


def score_values(answer: dict | None, env: MailboxEnv, secret_match: bool) -> dict[str, float | int]:
    """Calculate the legacy score tuple. Malformed or absent answers score as not found."""

    answer = answer if isinstance(answer, dict) else {}
    found = int(answer.get("found") is True)
    secret = answer.get("secret", "")
    if not isinstance(secret, str):
        secret = ""
    evidence = answer.get("evidence_email_ids", [])
    if not isinstance(evidence, list):
        evidence = []
    precision, recall = env.clue_precision_recall([str(item).strip() for item in evidence])
    match = int(bool(secret_match)) if found else 0
    final = round(found * match * recall * precision, 3)
    return {
        "found": found,
        "secret_match": match,
        "ev_recall": recall,
        "ev_precision": precision,
        "final": final,
    }


def reset_resource_cache() -> None:
    """Testing hook for deterministic rebuild checks."""

    _resources.cache_clear()
