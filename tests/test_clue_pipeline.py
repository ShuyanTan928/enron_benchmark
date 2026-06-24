"""Tests for the four-step clue pipeline (Step 3 + Step 4 unit coverage)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from src.clue_pipeline.generator import (
    ABANDONED_AMBIGUITY,
    ABANDONED_UNOBSERVABLE,
    ACCEPTED,
    _detect_trajectory_outcome,
    _draft_clue,
    _target_state_assignment,
    inner_loop,
)
from src.clue_pipeline.jury import (
    _CATEGORY_BADNESS,
    _parse_top3,
    _parse_verdict_object,
    categorical_verdict,
)
from src.clue_pipeline.schema import (
    Clue,
    ClueText,
    InnerLoopAttempt,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_engine(responses: list[str]):
    """Returns an object whose .generate() pops responses in order."""
    engine = MagicMock()
    iterator = iter(responses)

    def _generate(*args, **kwargs):
        try:
            return [next(iterator)]
        except StopIteration:
            return [""]

    engine.generate.side_effect = _generate
    engine.model_name = "mock-model"
    return engine


def _verdict_json(category: str, inference: str = "x") -> str:
    return json.dumps({"category": category, "inference": inference})


def _clue_draft_json(text: str = "Alice was seen with EPA documents.") -> str:
    return json.dumps({
        "text": text,
        "alternative_explanations": [
            "Standard regulatory review",
            "Background reading for a new project",
            "Routine compliance work",
        ],
    })


# ---------------------------------------------------------------------------
# Schema sanity
# ---------------------------------------------------------------------------

class TestSchema:
    def test_clue_text_round_trip(self):
        ct = ClueText(
            clue_id="S01-C1",
            fact_id="F1",
            dimension="document_access",
            text="example",
            alternative_explanations=["a", "b", "c"],
            target_state="NEUTRAL",
            final_jury_category="NEUTRAL",
            inner_loop_trajectory=[
                InnerLoopAttempt(attempt=0, text="example", category="NEUTRAL", inference="ok"),
            ],
        )
        data = ct.model_dump()
        assert data["target_state"] == "NEUTRAL"
        ct2 = ClueText.model_validate(data)
        assert ct2.inner_loop_trajectory[0].category == "NEUTRAL"

    def test_clue_email_round_trip(self):
        c = Clue(
            clue_id="S01-C1",
            fact_id="F1",
            dimension="document_access",
            text="example",
            sender_email="a@b.com",
            receiver_email="c@d.com",
            subject="Re: hi",
            body="hello",
        )
        c2 = Clue.model_validate(c.model_dump())
        assert c2.email_surfacing_degraded is False


# ---------------------------------------------------------------------------
# Jury — parsing + categorical voting
# ---------------------------------------------------------------------------

class TestJury:
    def test_parse_verdict_object_clean(self):
        obj = _parse_verdict_object(_verdict_json("LEAKED", "hidden activity"))
        assert obj == {"category": "LEAKED", "inference": "hidden activity"}

    def test_parse_verdict_object_with_fences(self):
        obj = _parse_verdict_object("```json\n" + _verdict_json("NEUTRAL", "fine") + "\n```")
        assert obj["category"] == "NEUTRAL"

    def test_parse_top3_basic(self):
        text = "1. First hypothesis.\n2. Second one.\n3. Third one.\n"
        assert _parse_top3(text) == ["First hypothesis.", "Second one.", "Third one."]

    def test_categorical_verdict_single_engine(self):
        engine = _mock_engine([_verdict_json("NEUTRAL", "routine")])
        worst, per_engine = categorical_verdict("text", [engine])
        assert worst.category == "NEUTRAL"
        assert len(per_engine) == 1

    def test_categorical_verdict_multi_family_worst_wins(self):
        e_neutral = _mock_engine([_verdict_json("NEUTRAL", "fine")])
        e_leaked = _mock_engine([_verdict_json("LEAKED", "covert")])
        worst, _ = categorical_verdict("text", [e_neutral, e_leaked])
        assert worst.category == "LEAKED"

    def test_off_topic_blocks_suspicious(self):
        # OFF_TOPIC is worse than SUSPICIOUS in our ordering
        e_off = _mock_engine([_verdict_json("OFF_TOPIC", "empty")])
        e_sus = _mock_engine([_verdict_json("SUSPICIOUS", "hmm")])
        worst, _ = categorical_verdict("text", [e_off, e_sus])
        assert worst.category == "OFF_TOPIC"

    def test_category_badness_ordering(self):
        assert _CATEGORY_BADNESS["LEAKED"] > _CATEGORY_BADNESS["OFF_TOPIC"]
        assert _CATEGORY_BADNESS["OFF_TOPIC"] > _CATEGORY_BADNESS["SUSPICIOUS"]
        assert _CATEGORY_BADNESS["SUSPICIOUS"] > _CATEGORY_BADNESS["NEUTRAL"]

    def test_invalid_category_defaults_to_off_topic(self):
        engine = _mock_engine([
            json.dumps({"category": "GARBAGE", "inference": "x"}),
            json.dumps({"category": "GARBAGE", "inference": "x"}),
        ])
        worst, _ = categorical_verdict("text", [engine])
        # After 2 invalid attempts the helper defaults to OFF_TOPIC
        assert worst.category == "OFF_TOPIC"


# ---------------------------------------------------------------------------
# Step 3 — Inner loop trajectory rules
# ---------------------------------------------------------------------------

class TestTrajectoryRules:
    def test_all_leaked_marks_ambiguity(self):
        traj = [
            InnerLoopAttempt(attempt=0, text="a", category="LEAKED", inference=""),
            InnerLoopAttempt(attempt=1, text="b", category="LEAKED", inference=""),
            InnerLoopAttempt(attempt=2, text="c", category="LEAKED", inference=""),
        ]
        outcome = _detect_trajectory_outcome(traj, max_retries=2)
        assert outcome == ABANDONED_AMBIGUITY

    def test_off_topic_after_leaked_means_unobservable(self):
        traj = [
            InnerLoopAttempt(attempt=0, text="a", category="LEAKED", inference=""),
            InnerLoopAttempt(attempt=1, text="b", category="OFF_TOPIC", inference=""),
            InnerLoopAttempt(attempt=2, text="c", category="OFF_TOPIC", inference=""),
        ]
        outcome = _detect_trajectory_outcome(traj, max_retries=2)
        assert outcome == ABANDONED_UNOBSERVABLE

    def test_oscillation_with_earlier_acceptable_reverts(self):
        # NEUTRAL → LEAKED → LEAKED: revert to the earlier NEUTRAL
        traj = [
            InnerLoopAttempt(attempt=0, text="a", category="NEUTRAL", inference=""),
            InnerLoopAttempt(attempt=1, text="b", category="LEAKED", inference=""),
            InnerLoopAttempt(attempt=2, text="c", category="LEAKED", inference=""),
        ]
        outcome = _detect_trajectory_outcome(traj, max_retries=2)
        assert outcome == ACCEPTED


# ---------------------------------------------------------------------------
# Step 3 — Target state distribution
# ---------------------------------------------------------------------------

class TestTargetStateAssignment:
    def test_n3_initial_all_neutral(self):
        states = _target_state_assignment(3, n_suspicious=0)
        assert states == ["NEUTRAL", "NEUTRAL", "NEUTRAL"]

    def test_n3_one_promoted(self):
        states = _target_state_assignment(3, n_suspicious=1)
        assert states.count("SUSPICIOUS") == 1
        assert states.count("NEUTRAL") == 2

    def test_n3_caps_at_ceil_half(self):
        # ⌈3/2⌉ = 2 max SUSPICIOUS, at least 1 NEUTRAL
        states = _target_state_assignment(3, n_suspicious=3)
        assert states.count("SUSPICIOUS") == 2
        assert states.count("NEUTRAL") == 1

    def test_n4(self):
        # ⌈4/2⌉ = 2 max SUSPICIOUS
        states = _target_state_assignment(4, n_suspicious=10)
        assert states.count("SUSPICIOUS") == 2
        assert states.count("NEUTRAL") == 2


# ---------------------------------------------------------------------------
# Step 3 — _draft_clue validation
# ---------------------------------------------------------------------------

class TestDraftClue:
    def test_accepts_well_formed(self):
        engine = _mock_engine([_clue_draft_json("Saw Alice on a call.")])
        result = _draft_clue(
            fact_statement="Alice contacted an outsider.",
            actor_role="A regulatory analyst.",
            target_state="NEUTRAL",
            trajectory=[],
            engine=engine,
        )
        assert result["text"] == "Saw Alice on a call."
        assert len(result["alternative_explanations"]) == 3

    def test_rejects_fewer_than_three_alternatives(self):
        bad = json.dumps({"text": "x", "alternative_explanations": ["a", "b"]})
        good = _clue_draft_json("ok")
        engine = _mock_engine([bad, good])
        result = _draft_clue(
            fact_statement="f",
            actor_role="r",
            target_state="NEUTRAL",
            trajectory=[],
            engine=engine,
        )
        assert result["text"] == "ok"

    def test_propagates_failure_after_retries(self):
        engine = _mock_engine(["not json", "still not json", "again not json"])
        with pytest.raises(RuntimeError):
            _draft_clue(
                fact_statement="f",
                actor_role="r",
                target_state="NEUTRAL",
                trajectory=[],
                engine=engine,
            )


# ---------------------------------------------------------------------------
# Step 3 — inner_loop end-to-end
# ---------------------------------------------------------------------------

class TestInnerLoop:
    def test_accepts_on_first_neutral(self):
        gen = _mock_engine([_clue_draft_json("Saw it.")])
        jury = _mock_engine([_verdict_json("NEUTRAL", "routine")])
        outcome, traj, alts = inner_loop(
            fact_statement="f",
            actor_role="r",
            target_state="NEUTRAL",
            generator_engine=gen,
            jury_engines=[jury],
            max_retries=2,
        )
        assert outcome == ACCEPTED
        assert len(traj) == 1
        assert traj[0].category == "NEUTRAL"
        assert len(alts) == 3

    def test_retries_after_leaked(self):
        gen = _mock_engine([
            _clue_draft_json("First attempt — too obvious."),
            _clue_draft_json("Second attempt — more subtle."),
        ])
        jury = _mock_engine([
            _verdict_json("LEAKED", "covert activity"),
            _verdict_json("SUSPICIOUS", "something off"),
        ])
        outcome, traj, _ = inner_loop(
            fact_statement="f",
            actor_role="r",
            target_state="SUSPICIOUS",
            generator_engine=gen,
            jury_engines=[jury],
            max_retries=2,
        )
        assert outcome == ACCEPTED
        assert traj[0].category == "LEAKED"
        assert traj[1].category == "SUSPICIOUS"

    def test_three_leaked_abandons(self):
        gen = _mock_engine([_clue_draft_json("a"), _clue_draft_json("b"), _clue_draft_json("c")])
        jury = _mock_engine([
            _verdict_json("LEAKED", "x"),
            _verdict_json("LEAKED", "x"),
            _verdict_json("LEAKED", "x"),
        ])
        outcome, traj, _ = inner_loop(
            fact_statement="f",
            actor_role="r",
            target_state="NEUTRAL",
            generator_engine=gen,
            jury_engines=[jury],
            max_retries=2,
        )
        assert outcome == ABANDONED_AMBIGUITY
        assert len(traj) == 3
