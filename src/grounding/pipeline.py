"""Wire the Step-1 stages: gen_topic -> HyDE -> retrieve -> fit-judge -> specialize.

gen_topic produces a deliberately ABSTRACT secret; once fit-judge picks a same-kind anchor,
`specialize` rewrites the secret to fit that email's real specifics (or skips), so the secret is
genuinely grounded — not a generic idea matched to a look-alike email. Each proposal carries the
abstract topic, HyDE probes, candidates, the judge's pick, the specialized secret, and the
resolved anchor. The automatic NONE gate fires when nothing retrieved / judge picked nothing /
specialize skipped; final accept/reject is the downstream CHECK gate.
"""
from __future__ import annotations

import json
import re

from .corpus import Email
from .prompts import (TOPIC_GEN_PROMPT, HYDE_PROMPT, FIT_JUDGE_PROMPT,
                      SPECIALIZE_PROMPT, fill)
from .retrieval import HybridRetriever, tokenize

# ---------------------------------------------------------------------------
# Robust JSON extraction (models wrap in ```json, add prose, etc.)
# ---------------------------------------------------------------------------

def _balanced(text: str, open_ch: str, close_ch: str) -> str | None:
    start = text.find(open_ch)
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def parse_obj(raw: str) -> dict | None:
    blob = _balanced(raw, "{", "}")
    if not blob:
        return None
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        return None


def parse_arr(raw: str) -> list | None:
    blob = _balanced(raw, "[", "]")
    if not blob:
        return None
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# Dedup (lexical — cheap; the AVOID list in the prompt does the heavy lifting)
# ---------------------------------------------------------------------------

def _sig(topic: dict) -> set[str]:
    text = f"{topic.get('name','')} {topic.get('secret','')} {topic.get('either_or','')}"
    return set(tokenize(text))


def _scrub_firm(text: str) -> str:
    """Never let the real firm's name reach a written secret. Deterministic, applied at
    output time (same scrub-on-model-output principle we enforce on Step-2): Enron -> [firm].
    Catches compounds too (EnronOnline -> [firm]Online, Enron North America -> [firm] ...)."""
    return re.sub(r"Enron", "[firm]", text or "", flags=re.IGNORECASE)


def is_duplicate(topic: dict, accepted: list[dict], thresh: float = 0.5) -> bool:
    s = _sig(topic)
    if not s:
        return True
    for a in accepted:
        sa = _sig(a)
        if not sa:
            continue
        j = len(s & sa) / len(s | sa)
        if j >= thresh:
            return True
    return False


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------

def gen_topic(engine, category: str, accepted: list[dict], temperature: float = 0.8) -> dict | None:
    avoid = "\n".join(f"- {a['name']}: {a.get('secret','')}" for a in accepted) or "- (none yet)"
    prompt = fill(TOPIC_GEN_PROMPT, category=category, avoid=avoid)
    raw = engine.generate(prompt, max_tokens=600, temperature=temperature)[0]
    topic = parse_obj(raw)
    if topic and topic.get("name") and topic.get("either_or"):
        topic["category"] = category
        return topic
    return None


def gen_hyde(engine, topic: dict, temperature: float = 0.8) -> list[str]:
    tjson = json.dumps({k: topic[k] for k in ("name", "secret", "either_or")}, ensure_ascii=False, indent=2)
    prompt = fill(HYDE_PROMPT, topic=tjson)
    raw = engine.generate(prompt, max_tokens=900, temperature=temperature)[0]
    arr = parse_arr(raw)
    docs = [str(x) for x in arr if isinstance(x, str) and x.strip()] if arr else []
    return docs


def specialize(engine, topic: dict, anchor: Email, temperature: float = 0.4) -> dict | None:
    """Rewrite the abstract secret into a concrete one grounded on the picked email, or skip."""
    abstract = json.dumps({k: topic.get(k) for k in ("name", "secret", "either_or")},
                          ensure_ascii=False, indent=2)
    prompt = fill(SPECIALIZE_PROMPT, abstract=abstract,
                  **{"from": anchor.from_name, "subject": anchor.subject,
                     "body": anchor.body[:1500]})
    raw = engine.generate(prompt, max_tokens=500, temperature=temperature)[0]
    return parse_obj(raw)


def judge_fit(engine, topic: dict, candidates: list[Email], temperature: float = 0.1) -> dict | None:
    tjson = json.dumps({k: topic[k] for k in ("name", "secret", "either_or")}, ensure_ascii=False, indent=2)
    lines = []
    for e in candidates:
        v = e.for_judge()
        lines.append(f'[{v["id"]}] {v["date"]} {v["from"]} -> {v["to"]} | "{v["subject"]}"\n     {v["snippet"]}')
    prompt = fill(FIT_JUDGE_PROMPT, topic=tjson, candidates="\n".join(lines))
    raw = engine.generate(prompt, max_tokens=400, temperature=temperature)[0]
    return parse_obj(raw)


def propose_topic(engine, retriever: HybridRetriever, emails: list[Email],
                  category: str, avoid: list[dict], used_anchors: set | None = None,
                  k_retrieve: int = 40, k_judge: int = 12) -> dict:
    """One full proposal. status in {grounded, none, dup, gen_error, hyde_error}.

    `avoid` = topics the next generation must NOT duplicate (already-written AND
    already-rejected, so the one-at-a-time regenerate loop keeps moving to new ideas)."""
    topic = gen_topic(engine, category, avoid)
    if not topic:
        return {"status": "gen_error", "topic": None}
    if is_duplicate(topic, avoid):
        return {"status": "dup", "topic": topic}

    hyde = gen_hyde(engine, topic)
    queries = list(hyde) + [topic.get("either_or", ""), topic.get("secret", "")]
    if not hyde:
        # still try with the topic text alone
        if not any(tokenize(q) for q in queries):
            return {"status": "hyde_error", "topic": topic}

    ranked = retriever.retrieve(queries, k=k_retrieve)
    # Dedup near-identical corpus emails (the corpus has triplicated copies) so they don't eat
    # the fit-judge's candidate slots; fill up to k_judge DISTINCT emails from the ranking.
    cand_emails, seen = [], set()
    for i, _ in ranked:
        e = emails[i]
        if used_anchors and e.message_id in used_anchors:      # one anchor -> one topic
            continue
        sig = re.sub(r"\s+", " ", f"{e.subject} {e.body}").strip().lower()[:240]
        if sig in seen:
            continue
        seen.add(sig)
        cand_emails.append(e)
        if len(cand_emails) >= k_judge:
            break
    if not cand_emails:
        return {"status": "none", "topic": topic, "hyde": hyde, "candidates": []}

    verdict = judge_fit(engine, topic, cand_emails) or {}
    pick = verdict.get("pick")
    cand_view = [e.for_judge() for e in cand_emails]

    if not isinstance(pick, int) or not (0 <= pick < len(emails)):
        return {"status": "none", "topic": topic, "hyde": hyde,
                "candidates": cand_view, "verdict": verdict, "anchor": None}

    # Ground the abstract secret on the picked email's real specifics (or skip if it can't host it).
    anchor = emails[pick]
    spec = specialize(engine, topic, anchor) or {}
    if spec.get("skip") or not spec.get("secret"):
        return {"status": "none", "topic": topic, "hyde": hyde, "candidates": cand_view,
                "verdict": verdict, "specialize": spec, "anchor": None}
    grounded = {**topic,
                "name": _scrub_firm(spec.get("name") or topic.get("name")),
                "secret": _scrub_firm(spec["secret"]),
                "either_or": _scrub_firm(spec.get("either_or") or topic.get("either_or"))}

    return {
        "status": "grounded",
        "topic": grounded,
        "abstract_topic": topic,
        "hyde": hyde,
        "candidates": cand_view,
        "verdict": verdict,
        "specialize": spec,
        "anchor": anchor.anchor_dict(),
        "anchor_full_body": anchor.body[:1500],   # full text for the CHECK gate
    }


def propose_grounding(engine, retriever: HybridRetriever, emails: list[Email],
                      category: str, avoid: list[dict], used_anchors: set | None = None,
                      k_retrieve: int = 40, k_judge: int = 12) -> dict:
    """Gen-4 proposal: gen ABSTRACT topic -> HyDE -> retrieve -> fit-judge, then return the abstract
    secret together with the fit-judge's ranked anchor candidates (pick, then runner-up). No
    `specialize`: the secret stays abstract; the anchor is only a real CARRIER (a real document /
    company / matter + era) that the downstream Step-2 plot is freely built around. The plot+judge
    is the real gate, so there is no separate Step-1 CHECK here.

    status in {grounded, dup, gen_error, hyde_error, none}. On `grounded`, `anchors` is an ordered
    list of Email objects to try (best first) — the runner walks them until the plot passes."""
    topic = gen_topic(engine, category, avoid)
    if not topic:
        return {"status": "gen_error", "topic": None}
    if is_duplicate(topic, avoid):
        return {"status": "dup", "topic": topic}

    hyde = gen_hyde(engine, topic)
    queries = list(hyde) + [topic.get("either_or", ""), topic.get("secret", "")]
    if not hyde and not any(tokenize(q) for q in queries):
        return {"status": "hyde_error", "topic": topic}

    ranked = retriever.retrieve(queries, k=k_retrieve)
    cand_emails, seen = [], set()
    for i, _ in ranked:
        e = emails[i]
        if used_anchors and e.message_id in used_anchors:
            continue
        sig = re.sub(r"\s+", " ", f"{e.subject} {e.body}").strip().lower()[:240]
        if sig in seen:
            continue
        seen.add(sig)
        cand_emails.append(e)
        if len(cand_emails) >= k_judge:
            break
    if not cand_emails:
        return {"status": "none", "topic": topic, "hyde": hyde}

    verdict = judge_fit(engine, topic, cand_emails) or {}
    order: list[Email] = []
    for key in ("pick", "runner_up"):
        v = verdict.get(key)
        if isinstance(v, int) and 0 <= v < len(emails):
            e = emails[v]
            if e not in order and not (used_anchors and e.message_id in used_anchors):
                order.append(e)
    if not order:                       # judge gave nothing usable — fall back to top retrieval
        order = cand_emails[:1]
    return {"status": "grounded", "topic": topic, "hyde": hyde,
            "verdict": verdict, "anchors": order}
