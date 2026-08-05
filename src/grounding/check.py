"""The final write/regenerate gate.

A `Checker` wraps any engine that exposes `.generate(prompt, max_tokens, temperature)`
(VLLMEngine or APIEngine alike) and applies CHECK_PROMPT to a grounded candidate. It is
the strong second-tier judge that runs AFTER grounding, on the real anchor email's full
text, and returns {decision: write|regenerate, ...}.

Intended production form: SonnetChecker (or-claude-sonnet via the API engine). During
bring-up a human reviewer applies the same CHECK_PROMPT by hand.
"""
from __future__ import annotations

import json
from pathlib import Path

from .prompts import CHECK_PROMPT, fill
from .pipeline import parse_obj


def build_check_prompt(candidate: dict) -> str:
    t = candidate["topic"]
    a = candidate["anchor"]
    tjson = json.dumps({k: t.get(k) for k in ("name", "category", "secret", "true_fact", "false_belief")},
                       ensure_ascii=False, indent=2)
    return fill(
        CHECK_PROMPT,
        topic=tjson,
        carrier=candidate.get("verdict", {}).get("carrier", ""),
        **{"from": a.get("from", ""),
           "to": ", ".join(a.get("to", [])),
           "date": a.get("date", "")[:10],
           "subject": a.get("subject", ""),
           "body": candidate.get("anchor_full_body", a.get("snippet", ""))},
    )


class Checker:
    """Final gate over any `.generate()` engine."""

    def __init__(self, engine, temperature: float = 0.0, max_tokens: int = 400):
        self.engine = engine
        self.temperature = temperature
        self.max_tokens = max_tokens

    def check(self, candidate: dict) -> dict:
        prompt = build_check_prompt(candidate)
        raw = self.engine.generate(prompt, max_tokens=self.max_tokens,
                                   temperature=self.temperature)[0]
        v = parse_obj(raw) or {}
        decision = str(v.get("decision", "regenerate")).strip().lower()
        if decision not in ("write", "regenerate"):
            decision = "regenerate"
        return {"decision": decision,
                "failed_criteria": v.get("failed_criteria", []),
                "reason": v.get("reason", ""),
                "raw": raw}


def SonnetChecker(preset: str = "or-claude-sonnet", **kw) -> Checker:
    """Production gate: claude-sonnet via the API engine. Requires an API key in env."""
    from src.models.api_engine import APIEngine
    return Checker(APIEngine.from_preset(preset), **kw)


# ---------------------------------------------------------------------------
# Type-aware gate — selects the secrets best SUITED to a given secret_type.
# Applies prompts/topic_judge_<type>.md (e.g. topic_judge_lying.md, whose `assertable`
# check keeps only secrets where a clean POSITIVE false claim exists — true lying, not
# silence). decision=write iff EVERY check is PASS.
# ---------------------------------------------------------------------------
def build_type_check_prompt(candidate: dict, secret_type: str) -> str:
    from .prompts import CONCEALMENT_ACTS, compose_gate_checks, resolve_type
    t = candidate["topic"]
    # Secret-first topic is mechanism-agnostic: it carries one line `secret` + `category`, no
    # true_fact/false_belief/act (those are derived later, at atomize). So the gate judges the SECRET and
    # its register fit — not the concealing act, which is chosen downstream. No anchor here by design:
    # whether the carrier came from the anchor is settled in code (pipeline.carrier_drift).
    tjson = json.dumps({k: t.get(k) for k in ("name", "secret", "category")},
                       ensure_ascii=False, indent=2)
    register, mechanism = resolve_type(t.get("category", "casual"), secret_type)
    if mechanism in CONCEALMENT_ACTS:          # commission/omission/paltering share ONE register-aware gate
        reg_check, _ = compose_gate_checks(register, mechanism)
        judge = (Path("prompts/topic_judge_concealment.md").read_text()
                 .replace("<<REGISTER_CHECK>>", reg_check))
    else:
        judge = Path(f"prompts/topic_judge_{secret_type}.md").read_text()   # unknown type: its own file
    return judge.replace("<<CANDIDATE>>", tjson)


class TypeChecker:
    """Gate that applies the secret_type's topic-judge; write iff every check PASSes."""

    def __init__(self, secret_type: str, engine, temperature: float = 0.0, max_tokens: int = 900):
        self.secret_type = secret_type
        self.engine = engine
        self.temperature = temperature
        self.max_tokens = max_tokens

    def check(self, candidate: dict) -> dict:
        raw = self.engine.generate(build_type_check_prompt(candidate, self.secret_type),
                                   max_tokens=self.max_tokens, temperature=self.temperature)[0]
        v = parse_obj(raw) or {}
        checks = [(k, val) for k, val in v.items() if isinstance(val, dict) and "verdict" in val]
        # Only a FAIL sinks a secret. WEAK = "holds, but not the strongest version" — rejecting on
        # WEAK made a 6-check conjunctive gate perfectionist and threw away usable secrets.
        fails = [k for k, val in checks if val.get("verdict", "").upper() == "FAIL"]
        ok = bool(checks) and not fails
        reason = v.get("fix", "") or "; ".join(
            f"{k}:{(val.get('reason', '') or '')[:60]}" for k, val in checks
            if val.get("verdict", "").upper() == "FAIL")
        return {"decision": "write" if ok else "regenerate",
                "failed_criteria": fails, "reason": reason[:200], "raw": raw}
