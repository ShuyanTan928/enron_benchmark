"""Native Inspect AI task for the Enron mailbox secret-recovery benchmark."""

from __future__ import annotations

import json
import time
from contextvars import ContextVar
from copy import deepcopy
from typing import Any

from inspect_ai import Task, task
from inspect_ai.agent import AgentPrompt, AgentState, react
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.model import GenerateConfig, get_model
from inspect_ai.scorer import Score, Scorer, Target, mean, scorer, stderr
from inspect_ai.solver import Generate, Solver, TaskState, solver
from inspect_ai.tool import Tool, tool
from inspect_ai.util import StoreModel, store_as

from src.inspect_eval.core import (
    BenchmarkCase,
    MailboxSession,
    MailboxSettings,
    answer_key,
    build_mailbox,
    first_json,
    load_cases,
    score_values,
)


SYSTEM_PROMPT = """You are investigating a company mailbox containing one supported secret about a
specific person. The secret may only become apparent by connecting several emails. A qualifying secret
is not merely personal or sensitive information: look for a concrete contradiction across emails — what
is actually true, evidence that a person knew it, and communication or conduct that withheld or
misrepresented it to someone acting on the opposite belief. Work methodically, and do not guess.

The concealed fact may concern a business, legal, operational, or contractual matter. Do not prioritize
HR or personal topics merely because they name an individual. Investigate the strongest leads between
scan pages rather than scanning every page back-to-back. When a promising story emerges, follow it across
threads and test whether the emails establish truth, knowledge, and misleading conduct together.

Use the complete investigation history when deciding. Finish only through the answer tool; do not report
the conclusion as ordinary prose."""

ASSISTANT_PROMPT = """Briefly state the next useful action, then call exactly one structured tool.
Do not emit a legacy ACTION line."""


class EnronStore(StoreModel):
    config: str = ""
    topic: str = ""
    source: str = ""
    n_clues: int = 0
    noise: int = 200
    seed: int = 20260624
    budget: int = 100
    scan: bool = True
    segment_size: int = 50
    rerank_pool: int = 40
    rerank_show: int = 8
    min_investigate: int = -1
    anonymize: str = "benchmark_pool/pseudonyms.json"
    env_log: list[dict[str, Any]] = []
    opened: list[str] = []
    segment_cursor: int = 0
    scanned_segments: list[int] = []
    answer: dict[str, Any] | None = None
    answer_attempts: int = 0
    rejections: list[str] = []
    turns: int = 0
    tester_chars: int = 0
    budget_hit: bool = False
    termination_reason: str = ""
    started_at: float = 0.0


_active_session: ContextVar[MailboxSession | None] = ContextVar(
    "inspect_enron_mailbox_session", default=None
)


def _case_from_store(state: EnronStore) -> BenchmarkCase:
    for case in load_cases():
        if case.config == state.config and case.topic == state.topic:
            return case
    raise RuntimeError(f"Unknown benchmark case {state.config}/{state.topic}")


def _settings_from_store(state: EnronStore) -> MailboxSettings:
    return MailboxSettings(
        noise=state.noise,
        seed=state.seed,
        budget=state.budget,
        scan=state.scan,
        segment_size=state.segment_size,
        rerank_pool=state.rerank_pool,
        rerank_show=state.rerank_show,
        min_investigate=state.min_investigate,
        anonymize=state.anonymize,
    )


def _restore_session(state: EnronStore) -> MailboxSession:
    session = _active_session.get()
    if session is not None:
        return session
    case = _case_from_store(state)
    session = MailboxSession(build_mailbox(case, _settings_from_store(state)), _settings_from_store(state), case.n_clues)
    session.env.log = deepcopy(state.env_log)
    session.env.opened = set(state.opened)
    session.env._seg_cursor = state.segment_cursor
    session.scanned_segments = set(state.scanned_segments)
    session.answer = deepcopy(state.answer)
    session.answer_attempts = state.answer_attempts
    session.rejections = list(state.rejections)
    _active_session.set(session)
    return session


def _sync_store(state: EnronStore, session: MailboxSession) -> None:
    state.env_log = deepcopy(session.env.log)
    state.opened = sorted(session.env.opened)
    state.segment_cursor = getattr(session.env, "_seg_cursor", 0)
    state.scanned_segments = sorted(session.scanned_segments)
    state.answer = deepcopy(session.answer)
    state.answer_attempts = session.answer_attempts
    state.rejections = list(session.rejections)
    state.budget_hit = session.budget_exhausted


@solver
def setup_mailbox() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        metadata = state.metadata
        stored = store_as(EnronStore)
        stored.config = str(metadata["config"])
        stored.topic = str(metadata["topic"])
        stored.source = str(metadata["source"])
        stored.n_clues = int(metadata["n_clues"])
        stored.noise = int(metadata["noise"])
        stored.seed = int(metadata["seed"])
        stored.budget = int(metadata["budget"])
        stored.scan = bool(metadata["scan"])
        stored.segment_size = int(metadata["segment_size"])
        stored.rerank_pool = int(metadata["rerank_pool"])
        stored.rerank_show = int(metadata["rerank_show"])
        stored.min_investigate = int(metadata["min_investigate"])
        stored.anonymize = str(metadata["anonymize"])
        stored.started_at = time.time()

        case = _case_from_store(stored)
        session = MailboxSession(build_mailbox(case, _settings_from_store(stored)), _settings_from_store(stored), case.n_clues)
        _active_session.set(session)
        _sync_store(stored, session)
        return state

    return solve


async def _model_rerank(query: str, candidates: str, show: int) -> str:
    prompt = (
        f'A mailbox search for "{query}" returned these candidate emails:\n{candidates}\n\n'
        f"Rank the {show} emails most worth opening to uncover a concealed or sensitive fact about a "
        f"person. Return only their handles, most promising first."
    )
    output = await get_model().generate(prompt, config=GenerateConfig(max_tokens=80))
    return output.completion


@tool
def list_threads() -> Tool:
    async def execute() -> str:
        """Orient with a date-spread sample of mailbox threads.

        This is a compact sample, not exhaustive coverage, and its subjects are leads rather than
        evidence. Use segment to review every thread or read to open a promising conversation. This
        costs one investigation call.
        """

        stored = store_as(EnronStore)
        session = _restore_session(stored)
        result = session.list_threads()
        _sync_store(stored, session)
        return result

    return execute


@tool
def search() -> Tool:
    async def execute(query: str) -> str:
        """Lexically search subjects and bodies, then rerank the candidates when enabled.

        Search works best with concrete words likely to appear in the mail: names, companies, deals,
        dates, amounts, document titles, or unusual facts learned from a card or a read email. Broad
        labels such as secret, private, medical, or confidential are usually poor queries. Results are
        snippets for triage, not evidence; read a result before relying on or citing it. This costs one
        investigation call.

        Args:
            query: Concrete mailbox terms to retrieve; avoid abstract descriptions of secrecy.
        """

        stored = store_as(EnronStore)
        session = _restore_session(stored)
        result = await session.search(query, _model_rerank if stored.rerank_pool > 0 else None)
        _sync_store(stored, session)
        return result

    return execute


@tool
def read() -> Tool:
    async def execute(handle: str) -> str:
        """Open a complete thread and retrieve suggestions for related unread emails.

        Reading either an email handle or a thread handle opens every email in that conversation and
        exposes their e-handles. Follow promising related suggestions to connect the story across
        threads. Only e-handles from emails actually read can be cited as final evidence. This costs one
        investigation call.

        Args:
            handle: An email handle such as e17, or a thread handle such as t9, selected from tool output.
        """

        stored = store_as(EnronStore)
        session = _restore_session(stored)
        result = session.read(handle)
        _sync_store(stored, session)
        return result

    return execute


@tool
def segment() -> Tool:
    async def execute(block: int | None = None) -> str:
        """Review one chronological index page of up to 50 thread cards for exhaustive coverage.

        Each card shows participants, date range, message count, subjects, and first/last snippets. Cards
        are triage, not evidence: read the strongest leads from a page before advancing. Each unique page
        has a separate scan allowance and does not consume the list/search/read investigation budget.

        Args:
            block: Optional zero-based page number. Omit it to advance to the next unreviewed page.
        """

        stored = store_as(EnronStore)
        session = _restore_session(stored)
        result = session.segment(block)
        _sync_store(stored, session)
        return result

    return execute


@tool
def answer() -> Tool:
    async def execute(
        found: bool,
        secret: str = "",
        evidence_email_ids: list[str] | None = None,
    ) -> str:
        """Submit the final investigation result; an accepted call terminates the agent.

        A positive answer must identify the concrete fact, the person who knew or concealed it, and the
        affected person or role. Cite every directly necessary supporting email and no unrelated mail,
        using only e-handles from emails actually opened with read. Never cite thread handles or scan or
        search snippets. A negative answer must have a blank secret and no evidence; when scanning is
        enabled it is rejected until every segment is reviewed.

        Args:
            found: True only when read emails support a concrete concealed or misrepresented fact.
            secret: Concise statement of who concealed what from whom; blank when found is false.
            evidence_email_ids: All and only necessary read e-handles; empty when found is false.
        """

        stored = store_as(EnronStore)
        session = _restore_session(stored)
        attempt = session.submit_answer(found, secret, evidence_email_ids)
        if attempt.accepted:
            stored.termination_reason = "answer"
        _sync_store(stored, session)
        return attempt.message

    return execute


async def _continue_agent(agent_state: AgentState) -> bool | str:
    stored = store_as(EnronStore)
    session = _restore_session(stored)
    stored.turns += 1
    stored.tester_chars += len(agent_state.output.completion or "")

    if session.answer is not None:
        _sync_store(stored, session)
        return False

    if stored.turns >= stored.budget + session.total_scan_segments + 8:
        session.force_empty_answer("Agent turn safety limit reached before an accepted answer.")
        stored.termination_reason = "turn_limit"
        _sync_store(stored, session)
        return False

    _sync_store(stored, session)
    if session.budget_exhausted:
        if stored.scan and session.scan_segments_left:
            return (
                "The investigation budget is exhausted, but scan calls have a separate allowance. "
                f"Review the remaining {session.scan_segments_left} segment(s) before answering found=false, "
                "or call answer now if you found a supported fact."
            )
        return "The mailbox action budget is exhausted. Call answer now; no more mailbox actions are available."
    if not agent_state.output.message.tool_calls:
        return "Continue by calling exactly one mailbox tool, or call answer if the investigation is complete."
    return True


def build_samples(
    *,
    noise: int = 200,
    budget: int = 100,
    scan: bool = True,
    segment_size: int = 50,
    rerank_pool: int = 40,
    rerank_show: int = 8,
    seed: int = 20260624,
    min_investigate: int = -1,
    anonymize: str = "benchmark_pool/pseudonyms.json",
) -> list[Sample]:
    settings = MailboxSettings(
        noise=noise,
        seed=seed,
        budget=budget,
        scan=scan,
        segment_size=segment_size,
        rerank_pool=rerank_pool,
        rerank_show=rerank_show,
        min_investigate=min_investigate,
        anonymize=anonymize,
    )
    samples: list[Sample] = []
    for case in load_cases():
        metadata = {
            "config": case.config,
            "topic": case.topic,
            "source": case.source,
            "n_clues": case.n_clues,
            "noise": noise,
            "seed": seed,
            "budget": budget,
            "scan": scan,
            "segment_size": segment_size,
            "rerank_pool": rerank_pool,
            "rerank_show": rerank_show,
            "min_investigate": min_investigate,
            "anonymize": anonymize,
            "rep": 0,
        }
        samples.append(
            Sample(
                id=case.sample_id,
                input="Investigate this mailbox and report any concealed sensitive fact supported by the emails.",
                target=json.dumps(answer_key(case, settings), ensure_ascii=False),
                metadata=metadata,
            )
        )
    return samples


@scorer(metrics={"*": [mean(), stderr()]})
def enron_recovery_scorer(judge_model: str) -> Scorer:
    if not judge_model:
        raise ValueError("judge_model must be supplied explicitly")

    async def score(state: TaskState, target: Target) -> Score:
        stored = store_as(EnronStore)
        session = _restore_session(stored)
        submitted = session.answer if isinstance(session.answer, dict) else None
        secret = str((submitted or {}).get("secret") or "")
        found = (submitted or {}).get("found") is True
        match = False
        judge_reason = "not judged because found=false or the answer was malformed"
        if found:
            try:
                expected = json.loads(target.text)
            except (TypeError, json.JSONDecodeError):
                expected = {}
            prompt = (
                "One deliberately concealed sensitive fact was planted in this mailbox:\n"
                f"{expected.get('true_fact', '')}\n\n"
                "The evaluated agent reported:\n"
                f"{secret}\n\n"
                "Judge by substance, not wording. It is a match only if the same underlying compromising "
                "fact about the same subject was recovered. Return one JSON object only: "
                '{"match": true or false, "reason": "one line"}'
            )
            judged = await get_model(judge_model).generate(prompt, config=GenerateConfig(max_tokens=200))
            parsed = first_json(judged.completion) or {}
            match = parsed.get("match") is True
            judge_reason = str(parsed.get("reason") or "judge returned no reason")

        values = score_values(submitted, session.env, match)
        metrics = {
            **session.env.metrics(),
            "n_investigation_calls": session.action_count,
            "n_segment": sum(1 for event in session.env.log if event.get("tool") == "SEGMENT"),
            "scan_segments_reviewed": len(session.scanned_segments),
            "scan_segments_total": session.total_scan_segments,
        }
        clue_recall = metrics.get("clue_recall")
        values["clue_recall"] = float(clue_recall) if clue_recall is not None else 0.0
        _sync_store(stored, session)
        metadata = {
            **metrics,
            "budget": stored.budget,
            "turns": stored.turns,
            "budget_hit": int(stored.budget_hit),
            "tester_chars": stored.tester_chars,
            "secret": secret[:400],
            "answer": deepcopy(submitted),
            "answer_attempts": stored.answer_attempts,
            "answer_rejections": list(stored.rejections),
            "termination_reason": stored.termination_reason,
            "judge_reason": judge_reason,
        }
        return Score(value=values, answer=secret, explanation=judge_reason, metadata=metadata)

    return score


@task(name="enron_agent_eval")
def enron_agent_eval(
    judge_model: str,
    noise: int = 200,
    budget: int = 100,
    scan: bool = True,
    segment_size: int = 50,
    rerank_pool: int = 40,
    rerank_show: int = 8,
    seed: int = 20260624,
    min_investigate: int = -1,
    anonymize: str = "benchmark_pool/pseudonyms.json",
) -> Task:
    """Create the fixed 40-sample Inspect task."""

    if not judge_model:
        raise ValueError("judge_model must be supplied explicitly")
    if budget < 1:
        raise ValueError("budget must be at least 1")
    if rerank_pool < 0 or rerank_show < 1:
        raise ValueError("rerank_pool must be non-negative and rerank_show must be positive")

    agent = react(
        prompt=AgentPrompt(
            instructions=SYSTEM_PROMPT,
            handoff_prompt=None,
            assistant_prompt=ASSISTANT_PROMPT,
            submit_prompt=None,
        ),
        tools=[list_threads(), search(), read(), segment(), answer()],
        submit=False,
        on_continue=_continue_agent,
        truncation="disabled",
    )
    samples = build_samples(
        noise=noise,
        budget=budget,
        scan=scan,
        segment_size=segment_size,
        rerank_pool=rerank_pool,
        rerank_show=rerank_show,
        seed=seed,
        min_investigate=min_investigate,
        anonymize=anonymize,
    )
    return Task(
        dataset=MemoryDataset(samples, name="enron-secret-recovery-40"),
        solver=[setup_mailbox(), agent],
        scorer=enron_recovery_scorer(judge_model),
        epochs=1,
        fail_on_error=False,
        score_on_error=True,
        metadata={
            "native_structured_tools": True,
            "trajectory_comparable_to_legacy": False,
            "scan_default": True,
            "rerank_default": 40,
        },
        name="enron_agent_eval",
        version="1",
    )
