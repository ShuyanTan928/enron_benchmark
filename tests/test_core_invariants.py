"""Invariant tests for the scoring/anonymization core — the properties the paper relies on.

These run without any API key or model. They pin: thread-level precision/recall, the multiplicative
score gate, pseudonymization consistency, and the conjunctive subset enumeration.
"""

from __future__ import annotations

import importlib.util
import json
from collections import defaultdict
from pathlib import Path

import pytest

from src.inspect_eval.core import (
    MailboxSettings,
    build_mailbox,
    load_cases,
    score_values,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def env():
    case = load_cases()[0]
    return build_mailbox(case, MailboxSettings(scan=False))


def _clue_handles_by_thread(env):
    by_thread = defaultdict(list)
    for h in sorted(env.clue_handles):
        by_thread[env.thread_of[h]].append(h)
    return by_thread


def test_recall_and_precision_are_thread_level(env):
    by_thread = _clue_handles_by_thread(env)
    one_per_thread = [handles[0] for handles in by_thread.values()]

    # Citing one handle per clue thread → full recall, full precision.
    prec, rec = env.clue_precision_recall(one_per_thread)
    assert rec == 1.0
    assert prec == 1.0

    # Citing a SECOND handle from the same clue thread must not change either metric
    # (thread-level de-duplication).
    multi = next((v for v in by_thread.values() if len(v) >= 2), None)
    if multi is not None:
        prec2, rec2 = env.clue_precision_recall(one_per_thread + [multi[1]])
        assert (prec2, rec2) == (prec, rec)


def test_unrelated_citation_lowers_precision_not_recall(env):
    by_thread = _clue_handles_by_thread(env)
    one_per_thread = [handles[0] for handles in by_thread.values()]
    noise = next(h for h in env.msgs if h not in env.clue_handles)

    prec, rec = env.clue_precision_recall(one_per_thread + [noise])
    assert rec == 1.0            # all clue threads still hit
    assert prec < 1.0            # one cited thread is not a clue thread


def test_no_evidence_scores_zero(env):
    prec, rec = env.clue_precision_recall([])
    assert (prec, rec) == (0.0, 0.0)


def test_score_is_a_strict_product_gate(env):
    clue = sorted(env.clue_handles)[0]

    # found + matched + fully grounded → nonzero
    good = score_values(
        {"found": True, "secret": "x", "evidence_email_ids": [clue]}, env, secret_match=True
    )
    assert good["final"] > 0

    # secret does not match → final 0 even with perfect evidence
    bad_match = score_values(
        {"found": True, "secret": "x", "evidence_email_ids": [clue]}, env, secret_match=False
    )
    assert bad_match["secret_match"] == 0
    assert bad_match["final"] == 0.0

    # not found → everything 0
    not_found = score_values({"found": False}, env, secret_match=True)
    assert not_found["found"] == 0
    assert not_found["final"] == 0.0

    # malformed answer → 0, no crash
    assert score_values(None, env, secret_match=True)["final"] == 0.0


def test_pseudonymization_is_consistent_and_scrubs_identity():
    from src.agent.anonymize import anon_text, build_subs

    subs = build_subs()
    line = "Tana Jones emailed Richard Sanders from tana.jones@enron.com"
    out1 = anon_text(line, subs)
    out2 = anon_text(line, subs)

    assert out1 == out2                       # deterministic
    assert "Tana Jones" not in out1           # real name scrubbed
    assert "enron.com" not in out1.lower()    # domain scrubbed


def test_paired_control_has_no_clue_but_same_background():
    from src.inspect_eval.core import (
        MailboxSettings,
        answer_key,
        build_mailbox,
        load_cases,
        make_controls,
    )

    cases = load_cases()
    controls = make_controls(cases, 2)
    assert len(controls) == 2
    assert all(c.is_control for c in controls)
    assert all(c.sample_id.endswith("-ctrl") for c in controls)

    settings = MailboxSettings(scan=False)
    ctrl = controls[0]
    ctrl_env = build_mailbox(ctrl, settings)
    assert len(ctrl_env.clue_handles) == 0  # no planted clue in a control

    key = answer_key(ctrl, settings)
    assert key.get("secret") == "" and key.get("is_control") is True

    # its positive twin (same config/topic) DOES carry clues
    twin = next(c for c in cases if c.config == ctrl.config and c.topic == ctrl.topic)
    assert len(build_mailbox(twin, settings).clue_handles) > 0


def test_build_samples_appends_tagged_controls():
    from src.inspect_eval.task import build_samples

    base = build_samples(scan=False)
    with_controls = build_samples(scan=False, n_controls=3)
    assert len(with_controls) == len(base) + 3

    controls = [s for s in with_controls if s.metadata.get("is_control")]
    assert len(controls) == 3
    assert json.loads(controls[0].target).get("is_control") is True


def test_proper_subset_enumeration_is_exhaustive():
    # The human-audit builder enumerates exactly the same proper subsets the AND-check tests:
    # every nonempty proper subset (2**n - 2).
    spec = importlib.util.spec_from_file_location(
        "human_audit_build", ROOT / "scripts" / "human_audit_build.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert [tuple(s) for s in module.proper_subsets(2)] == [(1,), (2,)]
    assert [tuple(s) for s in module.proper_subsets(3)] == [
        (1,), (2,), (3,), (1, 2), (1, 3), (2, 3)
    ]
    for n in (2, 3, 4):
        assert sum(1 for _ in module.proper_subsets(n)) == 2**n - 2
