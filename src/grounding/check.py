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

from .prompts import CHECK_PROMPT, fill
from .pipeline import parse_obj


def build_check_prompt(candidate: dict) -> str:
    t = candidate["topic"]
    a = candidate["anchor"]
    tjson = json.dumps({k: t[k] for k in ("name", "category", "secret", "either_or")},
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
