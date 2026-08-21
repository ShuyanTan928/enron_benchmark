import asyncio
import csv
import importlib.util

import pytest

from src.inspect_eval.core import (
    DEFAULT_TOPICS,
    LEGACY_CSV_FIELDS,
    MailboxSession,
    MailboxSettings,
    build_mailbox,
    first_json,
    investigation_credit,
    load_cases,
    reset_resource_cache,
    score_values,
)


@pytest.fixture(scope="module")
def case():
    return load_cases()[0]


def make_session(case, **overrides):
    values = {
        "noise": 8,
        "budget": 25,
        "scan": True,
        "segment_size": 3,
        "rerank_pool": 0,
        "min_investigate": 0,
    }
    values.update(overrides)
    settings = MailboxSettings(**values)
    return MailboxSession(build_mailbox(case, settings), settings, case.n_clues)


def test_default_matrix_is_exact_and_unique():
    assert MailboxSettings().segment_size == 50
    cases = load_cases()
    assert len(cases) == 40
    assert len({case.sample_id for case in cases}) == 40
    assert [case.topic for case in cases[:10]] == list(DEFAULT_TOPICS)
    assert sum(case.n_clues == 2 for case in cases) == 20
    assert sum(case.n_clues == 3 for case in cases) == 20
    assert {case.config for case in cases} == {"com_n2", "com_n3", "pal_n2", "pal_n3"}


def test_mailbox_construction_is_deterministic_anonymized_and_has_exact_noise(case):
    settings = MailboxSettings(noise=7, rerank_pool=0)
    reset_resource_cache()
    first = build_mailbox(case, settings)
    reset_resource_cache()
    second = build_mailbox(case, settings)
    fingerprint = lambda env: [
        (handle, msg["message_id"], msg.get("subject", ""), msg.get("body", ""))
        for handle, msg in env.msgs.items()
    ]
    assert fingerprint(first) == fingerprint(second)
    assert len(first.thread_msgs) == settings.noise + case.n_clues
    rendered = " ".join(msg.get("body", "") for msg in first.msgs.values())
    assert "Sara Shackleton" not in rendered


def test_list_invalid_read_expansion_and_metrics(case):
    session = make_session(case)
    assert "threads in this mailbox" in session.list_threads()
    before = session.action_count
    assert "no email" in session.read("e999999")
    assert session.action_count == before + 1

    clue = sorted(session.env.clue_handles)[0]
    text = session.read(clue)
    assert "Related emails about this matter:" in text
    assert session.env.log[-1]["tool"] == "READ"
    assert all(event["tool"] != "EXPAND" for event in session.env.log)
    metrics = session.env.metrics()
    assert metrics["n_tool_calls"] == session.action_count
    assert metrics["n_read"] == 2
    assert metrics["n_clues_read"] >= 1


def test_search_reranking_uses_model_order_and_falls_back(case):
    session = make_session(case, rerank_pool=40, rerank_show=2)
    seen = {}

    async def reranker(query, candidates, show):
        handles = [line.split(" |", 1)[0] for line in candidates.splitlines() if line.startswith("e")]
        seen["pool"] = handles
        return " ".join(reversed(handles[-2:]))

    result = asyncio.run(session.search("contract capacity status", reranker))
    returned = [line.split(" |", 1)[0] for line in result.splitlines() if line.startswith("e")]
    assert returned == list(reversed(seen["pool"][-2:]))
    assert session.env.log[-1]["tool"] == "SEARCH"
    assert len(session.env.log[-1]["returned"]) >= len(returned)

    async def invalid_reranker(query, candidates, show):
        return "not handles"

    fallback = make_session(case, rerank_pool=40, rerank_show=2)
    result = asyncio.run(fallback.search("contract capacity status", invalid_reranker))
    top = fallback.env.log[-1]["returned"][:2]
    assert [line.split(" |", 1)[0] for line in result.splitlines()] == top


def test_segment_cursor_tracks_unique_full_coverage(case):
    session = make_session(case, segment_size=3)
    total = session.scan_segments_left
    session.segment(1)
    assert session.scan_segments_left == total - 1
    session.segment(1)
    assert session.scan_segments_left == total - 1
    for block in range(total):
        session.segment(block)
    assert session.scan_segments_left == 0


def test_answer_rejects_insufficient_investigation(case):
    session = make_session(case, min_investigate=2, scan=False)
    attempt = session.submit_answer(True, "guess", [])
    assert not attempt.accepted
    assert "at least 2" in attempt.message

    asyncio.run(session.search("contract"))
    asyncio.run(session.search("contract"))
    assert investigation_credit(session.env) == 1


def test_answer_rejects_unread_search_results(case):
    session = make_session(case, scan=False)
    asyncio.run(session.search("contract capacity"))
    attempt = session.submit_answer(True, "claim", [])
    assert not attempt.accepted
    assert "Unread search results" in attempt.message


def test_negative_answer_requires_complete_scan(case):
    session = make_session(case, scan=True)
    assert not session.submit_answer(False).accepted
    for block in range(session.scan_segments_left):
        session.segment(block)
    assert session.submit_answer(False).accepted


def test_budget_exhaustion_forces_answer_and_blocks_actions(case):
    session = make_session(case, budget=1, scan=True, min_investigate=99)
    session.list_threads()
    assert session.budget_exhausted
    assert "budget exhausted" in session.read("e1").lower()
    assert session.action_count == 1
    assert session.submit_answer(False).accepted


def test_score_math_partial_evidence_and_malformed_answer(case):
    session = make_session(case, scan=False)
    clue = sorted(session.env.clue_handles)[0]
    noise = next(handle for handle in session.env.msgs if handle not in session.env.clue_handles)
    partial = score_values(
        {"found": True, "secret": "right fact", "evidence_email_ids": [clue, noise]},
        session.env,
        secret_match=True,
    )
    assert partial["found"] == 1
    assert partial["secret_match"] == 1
    assert partial["ev_precision"] == 0.5
    assert partial["ev_recall"] == 0.5
    assert partial["final"] == 0.25
    assert score_values({"found": "true", "evidence_email_ids": "e1"}, session.env, True)["final"] == 0
    assert score_values(None, session.env, True)["found"] == 0


def test_first_json_handles_braces_inside_strings():
    assert first_json('prefix {"match": true, "reason": "has { detail }"} suffix')["match"] is True
    assert first_json("not json") is None


def test_legacy_csv_header_is_exact_and_csv_readable(tmp_path):
    expected = (
        "config,topic,control,rep,budget,found,secret_match,ev_recall,ev_precision,final,"
        "false_positive,n_tool_calls,n_search,n_read,n_emails_opened,n_redundant_reads,"
        "n_clues_total,n_clues_read,clue_recall,turns,budget_hit,certified,latency_s,tester_chars,secret"
    ).split(",")
    assert list(LEGACY_CSV_FIELDS) == expected
    path = tmp_path / "rows.csv"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEGACY_CSV_FIELDS)
        writer.writeheader()
        writer.writerow({field: "" for field in LEGACY_CSV_FIELDS} | {"config": "com_n2", "final": 0.25})
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["config"] == "com_n2"
    assert float(rows[0]["final"]) == 0.25


@pytest.mark.skipif(importlib.util.find_spec("inspect_ai") is None, reason="Inspect AI not installed")
def test_inspect_mock_model_integration(tmp_path):
    from inspect_ai import eval
    from inspect_ai.model import ModelOutput, get_model
    from src.inspect_eval.task import enron_agent_eval

    model = get_model(
        "mockllm/model",
        custom_outputs=[
            ModelOutput.for_tool_call("mockllm/model", "answer", {"found": False, "secret": "", "evidence_email_ids": []})
        ],
    )
    task = enron_agent_eval(
        judge_model="mockllm/judge",
        noise=1,
        budget=2,
        scan=False,
        rerank_pool=0,
        min_investigate=0,
    )
    log = eval(task, model=model, limit=1, log_dir=str(tmp_path), display="none")[0]
    assert log.status == "success"
    assert log.samples and log.samples[0].scores
