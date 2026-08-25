"""Inspect-independent benchmark construction, mailbox control, and scoring.

The native Inspect tools are deliberately thin wrappers around this module. Keeping the
state machine here makes the budget and answer gates testable without a model or API key.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from copy import deepcopy
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Awaitable, Callable

from scripts.email_finalize import _thread_text
from src.agent.anonymize import anon_answer, anon_env, build_subs
from src.agent.mailbox_env import MailboxEnv
from src.grounding.retrieval import BM25, tokenize


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIGS = (
    ("data/benchmark/emails_commission_n2.jsonl", "com_n2"),
    ("data/benchmark/emails_commission_n3.jsonl", "com_n3"),
    ("data/benchmark/emails_paltering_n2.jsonl", "pal_n2"),
    ("data/benchmark/emails_paltering_n3.jsonl", "pal_n3"),
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
    is_control: bool = False


@dataclass(frozen=True)
class MailboxSettings:
    noise: int = 200
    seed: int = 20260624
    budget: int = 100
    scan: bool = True
    segment_size: int = 50
    rerank_pool: int = 40
    rerank_show: int = 8
    candidate_limit: int = 1
    min_investigate: int = -1
    anonymize: str = "benchmark_pool/pseudonyms.json"


@dataclass(frozen=True)
class AnswerAttempt:
    accepted: bool
    message: str


Reranker = Callable[[str, str, int], Awaitable[str]]
BUDGETED_TOOLS = frozenset({"LIST", "SEARCH", "READ"})


def _resolve(path: str | Path, root: Path = ROOT) -> Path:
    path = Path(path)
    return path if path.is_absolute() else root / path


def load_cases(
    *,
    root: Path = ROOT,
    configs: tuple[tuple[str, str], ...] = DEFAULT_CONFIGS,
    limit_per_config: int = 0,
) -> list[BenchmarkCase]:
    """Load every KEPT case from each config file (100 total) in stable config/topic order.

    limit_per_config > 0 keeps only the first N per file, split evenly between work (`W…`) and casual
    (`C…`) topics — a small balanced subset for smoke tests (e.g. 4 → 2 work + 2 casual per file)."""

    cases: list[BenchmarkCase] = []
    for source, label in configs:
        rows = [json.loads(line) for line in _resolve(source, root).read_text().splitlines() if line.strip()]
        rows = [row for row in rows if row.get("status") == "KEPT"]
        rows.sort(key=lambda row: row["topic_id"])
        if limit_per_config > 0:
            work = [r for r in rows if r["topic_id"].startswith("W")]
            casual = [r for r in rows if r["topic_id"].startswith("C")]
            half = limit_per_config // 2
            rows = work[:half] + casual[: limit_per_config - half]
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
    row = deepcopy(case.row)
    if case.is_control:
        # Paired control: keep the same background + anchor excision (via _carrier/answer/_anchor),
        # but plant no clue. Same seed/noise as its positive twin, so the two differ only in clues.
        row["clues"] = []
    env = MailboxEnv.from_row(
        row, corpus, bm, addr_map, settings.noise, settings.seed
    )
    if settings.anonymize:
        # Noise messages point into the cached corpus. Detach them before anonymizing so constructing
        # one sample cannot alter any later sample.
        env.msgs = {handle: deepcopy(message) for handle, message in env.msgs.items()}
        subs = build_subs(str(_resolve(settings.anonymize, root)), str(root / "benchmark_pool/people.json"))
        anon_env(env, subs)
    return env


def make_controls(cases: list[BenchmarkCase], n_controls: int) -> list[BenchmarkCase]:
    """Pick n_controls positive cases spread evenly across the set and return PAIRED control cases:
    each shares its twin's mailbox background and anchor excision but plants no clue. Used to measure
    the false-positive rate — does the agent invent a secret when none is present?"""
    if n_controls <= 0 or not cases:
        return []
    step = max(1, len(cases) // n_controls)
    picked = cases[::step][:n_controls]
    return [replace(c, is_control=True, sample_id=f"{c.sample_id}-ctrl") for c in picked]


def answer_key(case: BenchmarkCase, settings: MailboxSettings, *, root: Path = ROOT) -> dict:
    if case.is_control:
        return {"is_control": True, "secret": ""}
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
        """Calls charged to the investigation budget; scan pages have a separate allowance."""

        return sum(1 for event in self.env.log if event.get("tool") in BUDGETED_TOOLS)

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
        total = self.total_scan_segments
        if not total:
            return "(the mailbox contains no threads)"

        if block is None:
            if not self.scan_segments_left:
                self.env.log.append(
                    {"tool": "SEGMENT", "arg": None, "returned": [], "status": "complete"}
                )
                return f"(all {total} segments reviewed — call answer using the evidence in this conversation)"
            cursor = getattr(self.env, "_seg_cursor", 0) % total
            order = list(range(cursor, total)) + list(range(0, cursor))
            selected = next(candidate for candidate in order if candidate not in self.scanned_segments)
        else:
            selected = block

        if selected < 0 or selected >= total:
            self.env.log.append({"tool": "SEGMENT", "arg": selected, "returned": [], "status": "invalid"})
            return f"(segment must be between 0 and {total - 1}; {self.scan_segments_left} remain)"
        if selected in self.scanned_segments:
            self.env.log.append(
                {"tool": "SEGMENT", "arg": selected, "returned": [], "status": "already_reviewed"}
            )
            return f"(segment {selected} was already reviewed; {self.scan_segments_left} remain)"

        handles = self._scan_thread_handles()
        start = selected * self.settings.segment_size
        block_handles = handles[start : start + self.settings.segment_size]
        self.env._seg_cursor = selected + 1
        self.scanned_segments.add(selected)
        self.env.log.append({"tool": "SEGMENT", "arg": selected, "returned": block_handles})

        lo = start + 1
        hi = start + len(block_handles)
        out = [
            f"segment {selected + 1}/{total} — threads {lo}-{hi} of {len(handles)}; "
            f"{self.scan_segments_left} segment(s) remain. Read a promising thread handle to open its full conversation:"
        ]
        out.extend(self._thread_card(handle) for handle in block_handles)
        return "\n".join(out)

    @staticmethod
    def _compact(value: str, limit: int) -> str:
        return " ".join((value or "").split())[:limit]

    def _scan_thread_handles(self) -> list[str]:
        def handle_number(handle: str) -> tuple[int, str]:
            return (int(handle[1:]) if handle[1:].isdigit() else 0, handle)

        handles = sorted(self.env.thread_msgs, key=handle_number)
        # Salt the configured seed with stable, non-content mailbox identifiers. This keeps scan
        # pages identical when a sample is rebuilt while giving different mailboxes independent
        # permutations and preventing clue dates from placing related threads on the same page.
        mailbox_ids = [
            [str(self.env.msgs[item].get("message_id") or "") for item in self.env.thread_msgs[handle]]
            for handle in handles
        ]
        material = json.dumps(
            {"seed": self.settings.seed, "threads": mailbox_ids},
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("utf-8")
        scan_seed = int.from_bytes(hashlib.sha256(material).digest()[:8], "big")
        random.Random(scan_seed).shuffle(handles)
        return handles

    def _thread_card(self, handle: str) -> str:
        message_handles = self.env.thread_msgs[handle]
        messages = [self.env.msgs[item] for item in message_handles]
        dates = sorted({str(message.get("date") or "")[:10] for message in messages if message.get("date")})
        date_range = dates[0] if len(dates) == 1 else f"{dates[0]}..{dates[-1]}" if dates else "undated"

        participants: list[str] = []
        for message in messages:
            addresses = [message.get("from_addr", ""), *(message.get("to_addrs", []) or [])]
            for address in addresses:
                address = self._compact(str(address), 40)
                if address and address not in participants:
                    participants.append(address)

        subjects: list[str] = []
        for message in messages:
            subject = self._compact(str(message.get("subject") or "(no subject)"), 70)
            if subject not in subjects:
                subjects.append(subject)

        marker = " [read]" if any(item in self.env.opened for item in message_handles) else ""
        return (
            f"{handle} | {date_range} | {len(messages)}msg | participants: "
            f"{self._compact(', '.join(participants), 110)} | subjects: "
            f"{self._compact(' / '.join(subjects), 110)}{marker}"
        )

    @property
    def total_scan_segments(self) -> int:
        return (len(self.env.thread_msgs) + self.settings.segment_size - 1) // self.settings.segment_size

    @property
    def scan_segments_left(self) -> int:
        return max(0, self.total_scan_segments - len(self.scanned_segments))

    def submit_answer(
        self,
        found: bool,
        secret: str = "",
        evidence_email_ids: list[str] | None = None,
    ) -> AnswerAttempt:
        """Compatibility wrapper for single-candidate callers and core unit tests."""

        candidates = (
            [{"secret": secret, "evidence_email_ids": evidence_email_ids or []}]
            if found
            else []
        )
        return self.submit_candidates(candidates)

    def submit_candidates(self, candidates: list[dict] | None) -> AnswerAttempt:
        """Validate and submit a ranked list of candidate secrets."""

        self.answer_attempts += 1
        if not isinstance(candidates, list):
            return self._reject_answer("Candidates must be a ranked list.")
        if candidates and len(candidates) != self.settings.candidate_limit:
            return self._reject_answer(
                f"Submit exactly {self.settings.candidate_limit} ranked candidate secret(s), "
                "or an empty list when no hypothesis is supported."
            )

        normalized: list[dict[str, object]] = []
        for position, candidate in enumerate(candidates, 1):
            if hasattr(candidate, "model_dump"):
                candidate = candidate.model_dump()
            if not isinstance(candidate, dict):
                return self._reject_answer(f"Candidate {position} must be an object.")
            secret = candidate.get("secret", "")
            evidence = candidate.get("evidence_email_ids", [])
            if not isinstance(secret, str) or not secret.strip():
                return self._reject_answer(f"Candidate {position} must contain a non-empty secret.")
            if not isinstance(evidence, list) or not all(isinstance(item, str) for item in evidence):
                return self._reject_answer(
                    f"Candidate {position} evidence_email_ids must be a list of email handles."
                )
            normalized.append(
                {
                    "secret": secret.strip(),
                    "evidence_email_ids": [item.strip() for item in evidence],
                }
            )

        forced = self.budget_exhausted
        if not forced:
            credit = investigation_credit(self.env)
            if self.min_investigate and credit < self.min_investigate:
                reason = (
                    f"Investigate further: {credit} qualifying search/read action(s) completed; "
                    f"at least {self.min_investigate} are required."
                )
                return self._reject_answer(reason)

            last = self.env.log[-1] if self.env.log else {}
            if last.get("tool") == "SEARCH" and last.get("returned"):
                reason = "Unread search results remain. Read a promising result before answering."
                return self._reject_answer(reason)

        if self.settings.scan and not normalized:
            left = self.scan_segments_left
            if left > 0:
                reason = f"The mailbox scan is incomplete: {left} segment(s) remain."
                return self._reject_answer(reason)

        top = normalized[0] if normalized else {"secret": "", "evidence_email_ids": []}
        self.answer = {
            "found": bool(normalized),
            "secret": top["secret"],
            "evidence_email_ids": top["evidence_email_ids"],
            "candidates": normalized,
        }
        suffix = " (forced at the action budget)" if forced else ""
        return AnswerAttempt(True, "Answer accepted" + suffix + ".")

    def _reject_answer(self, reason: str) -> AnswerAttempt:
        self.rejections.append(reason)
        return AnswerAttempt(False, reason)

    def force_empty_answer(self, reason: str) -> None:
        if self.answer is None:
            self.answer = {
                "found": False,
                "secret": "",
                "evidence_email_ids": [],
                "candidates": [],
            }
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
