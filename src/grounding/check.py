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
    t = candidate["topic"]
    a = candidate["anchor"]
    tjson = json.dumps({k: t.get(k) for k in ("name", "secret", "true_fact", "false_belief")},
                       ensure_ascii=False, indent=2)
    anchor = (f'From: {a.get("from", "")}  ->  To: {", ".join(a.get("to", []))}   '
              f'({(a.get("date", "") or "")[:10]})\nSubject: "{a.get("subject", "")}"\n\n'
              f'{candidate.get("anchor_full_body", a.get("snippet", ""))}')
    judge = Path(f"prompts/topic_judge_{secret_type}.md").read_text()
    return judge.replace("<<ANCHOR>>", anchor).replace("<<CANDIDATE>>", tjson)


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
        fails = [k for k, val in checks if val.get("verdict", "").upper() != "PASS"]
        ok = bool(checks) and not fails
        reason = v.get("fix", "") or "; ".join(
            f"{k}:{(val.get('reason', '') or '')[:60]}" for k, val in checks
            if val.get("verdict", "").upper() != "PASS")
        return {"decision": "write" if ok else "regenerate",
                "failed_criteria": fails, "reason": reason[:200], "raw": raw}
