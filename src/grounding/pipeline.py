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
from .prompts import (TOPIC_GEN_PROMPT, HYDE_PROMPT, FIT_JUDGE_PROMPT, SPECIALIZE_PROMPT,
                      CONCEALMENT_ACTS, fill, resolve_type, build_topic_prompt)
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
    text = (f"{topic.get('name','')} {topic.get('secret','')} {topic.get('true_fact','')} "
            f"{topic.get('false_belief','')} {topic.get('act','')}")
    return set(tokenize(text))


def _scrub_firm(text: str) -> str:
    """Never let the real firm's name reach a written secret. Deterministic, applied at
    output time (same scrub-on-model-output principle we enforce on Step-2): Enron -> [firm].
    Catches compounds too (EnronOnline -> [firm]Online, Enron North America -> [firm] ...)."""
    return re.sub(r"Enron", "[firm]", text or "", flags=re.IGNORECASE)


_CARRIER_STOP = {"the", "a", "an", "of", "for", "with", "and", "to", "s", "our", "their", "its",
                 "agreement", "document", "letter", "notice", "filing", "form", "report", "status"}


def carrier_drift(carrier: str, anchor: Email, need: float = 0.5) -> list[str] | None:
    """None if the carrier really came from this email; otherwise the carrier words that aren't in it.

    Whether the carrier is the anchor's is a FACT — a word is in the email or it isn't — so it is
    checked here rather than spent on a judge. Generic nouns ("agreement", "notice") are dropped: they
    are in every email and would wave anything through. What must land is the DISTINCTIVE part (the
    counterparty, the docket number, the deal name)."""
    words = [w for w in tokenize(carrier or "") if w not in _CARRIER_STOP and len(w) > 2]
    if not words:
        return ["<no carrier given>"]
    have = set(tokenize(f"{anchor.subject} {anchor.body}"))
    absent = [w for w in words if w not in have]
    return None if len(absent) <= (1.0 - need) * len(words) else absent


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

def gen_topic(engine, category: str, accepted: list[dict], secret_type: str = "",
              temperature: float = 0.85) -> dict | None:
    # Secret-first, mechanism-agnostic: one one-line secret per register. The mechanism
    # (commission / omission / paltering) and the casting are decided later, at atomize, so
    # `secret_type` is accepted for caller compatibility but does NOT shape the topic — one secret
    # feeds all three mechanisms. Dedup is on the SECRET (the concrete matter), not the name.
    avoid = "\n".join(f"- {a.get('secret','')}" for a in accepted if a.get("secret")) or "(none yet)"
    prompt = build_topic_prompt(category, avoid)
    raw = engine.generate(prompt, max_tokens=400, temperature=temperature)[0]
    topic = parse_obj(raw)
    if topic and topic.get("name") and topic.get("secret"):
        topic["category"] = category
        return topic
    return None


def gen_hyde(engine, topic: dict, temperature: float = 0.8) -> list[str]:
    tjson = json.dumps({k: topic[k] for k in ("name", "secret", "true_fact", "false_belief") if k in topic}, ensure_ascii=False, indent=2)
    prompt = fill(HYDE_PROMPT, topic=tjson)
    raw = engine.generate(prompt, max_tokens=900, temperature=temperature)[0]
    arr = parse_arr(raw)
    docs = [str(x) for x in arr if isinstance(x, str) and x.strip()] if arr else []
    return docs


def specialize(engine, topic: dict, anchor: Email, temperature: float = 0.4,
               secret_type: str = "") -> dict | None:
    """Rewrite the abstract secret into a concrete one grounded on the picked email, or skip.

    The concealing act travels with the secret: grounding onto a new matter can silently break it
    (a paltering lever, in particular, has to be re-derived on THIS email's domain), so the
    mechanism's act clause is injected here too."""
    abstract = json.dumps({k: topic.get(k) for k in ("name", "secret", "true_fact", "false_belief", "act")},
                          ensure_ascii=False, indent=2)
    _, mech = resolve_type(topic.get("category", "work"), secret_type)
    prompt = fill(SPECIALIZE_PROMPT, abstract=abstract,
                  act_clause=CONCEALMENT_ACTS[mech]["act_clause"],
                  **{"from": anchor.from_name, "subject": anchor.subject,
                     "body": anchor.body[:1500]})
    raw = engine.generate(prompt, max_tokens=1000, temperature=temperature)[0]
    out = parse_obj(raw)
    if out is None:            # truncation / malformed JSON — NOT the same thing as "this email can't host it"
        return {"parse_error": True, "raw": raw[-300:]}
    return out


def judge_fit(engine, topic: dict, candidates: list[Email], temperature: float = 0.1) -> dict | None:
    tjson = json.dumps({k: topic[k] for k in ("name", "secret", "true_fact", "false_belief") if k in topic}, ensure_ascii=False, indent=2)
    lines = []
    for e in candidates:
        v = e.for_judge()
        lines.append(f'[{v["id"]}] {v["date"]} {v["from"]} -> {v["to"]} | "{v["subject"]}"\n     {v["snippet"]}')
    prompt = fill(FIT_JUDGE_PROMPT, topic=tjson, candidates="\n".join(lines))
    raw = engine.generate(prompt, max_tokens=400, temperature=temperature)[0]
    return parse_obj(raw)


def propose_topic(engine, retriever: HybridRetriever, emails: list[Email],
                  category: str, avoid: list[dict], used_anchors: set | None = None,
                  k_retrieve: int = 40, k_judge: int = 12, secret_type: str = "",
                  seen: list[dict] | None = None) -> dict:
    """One full proposal. status in {grounded, none, dup, gen_error, hyde_error}.

    `avoid` goes INTO THE PROMPT — so it holds only the secrets that were KEPT. A rejected secret is a
    bad example, and putting it in front of the model under any heading is still showing it one.
    `seen` never reaches the model: it is the lexical dedup set, and it may include the rejects, so the
    loop doesn't spend an attempt re-proposing an idea it already threw away."""
    seen = avoid if seen is None else seen
    topic = gen_topic(engine, category, avoid, secret_type=secret_type)
    if not topic:
        return {"status": "gen_error", "topic": None}
    if is_duplicate(topic, seen):
        return {"status": "dup", "topic": topic}

    hyde = gen_hyde(engine, topic)
    queries = list(hyde) + [topic.get("true_fact", ""), topic.get("false_belief", ""), topic.get("secret", "")]
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
    spec = specialize(engine, topic, anchor, secret_type=secret_type) or {}
    if spec.get("parse_error"):        # a broken response, not a verdict about this email — say so
        return {"status": "spec_error", "topic": topic, "hyde": hyde, "candidates": cand_view,
                "verdict": verdict, "specialize": spec, "anchor": None}
    if spec.get("skip") or not spec.get("secret"):
        return {"status": "none", "topic": topic, "hyde": hyde, "candidates": cand_view,
                "verdict": verdict, "specialize": spec, "anchor": None}

    # Is the carrier actually FROM this email, or invented? That is a fact, not a judgment — so it is
    # settled here, in code, and the LLM gate never sees the anchor at all.
    missing = carrier_drift(spec.get("carrier", ""), anchor)
    if missing is not None:
        return {"status": "carrier_drift", "topic": topic, "hyde": hyde, "candidates": cand_view,
                "verdict": verdict, "specialize": spec, "anchor": None,
                "drift": f"carrier {spec.get('carrier','')!r} not in the anchor (absent: {missing})"}

    # `act` must be taken from the SPECIALIZED secret. Keeping the abstract act next to a grounded
    # true_fact leaves the two describing different matters — the act no longer addresses the fact.
    grounded = {**topic,
                "name": _scrub_firm(spec.get("name") or topic.get("name")),
                "secret": _scrub_firm(spec["secret"]),
                "carrier": _scrub_firm(spec.get("carrier", "")),
                "true_fact": _scrub_firm(spec.get("true_fact") or topic.get("true_fact") or ""),
                "false_belief": _scrub_firm(spec.get("false_belief") or topic.get("false_belief") or ""),
                "act": _scrub_firm(spec.get("act") or topic.get("act") or "")}

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


def propose_ungrounded(engine, category: str, avoid: list[dict], secret_type: str = "",
                       seen: list[dict] | None = None) -> dict:
    """One CASUAL proposal — NO anchor. Casual secrets are personal matters not tied to a real
    corpus event, so we skip HyDE / retrieve / fit-judge / specialize entirely: just gen an abstract
    topic and hand it straight to the type gate. The concrete particulars are invented later at the
    SPEC step (there is no anchor to draw them from). status in {grounded, dup, gen_error}.

    `anchor` is None throughout — downstream (atomize_build era fallback, build_haystack excision) all
    tolerate a null anchor, so a casual item plants its clues in corpus noise with nothing to excise."""
    topic = gen_topic(engine, category, avoid, secret_type=secret_type)
    if not topic:
        return {"status": "gen_error", "topic": None}
    if is_duplicate(topic, avoid):
        return {"status": "dup", "topic": topic}
    grounded = {**topic,
                "name": _scrub_firm(topic.get("name", "")),
                "secret": _scrub_firm(topic.get("secret", "")),
                "true_fact": _scrub_firm(topic.get("true_fact", "")),
                "false_belief": _scrub_firm(topic.get("false_belief", ""))}
    return {"status": "grounded", "topic": grounded, "abstract_topic": topic,
            "anchor": None, "anchor_full_body": ""}


def propose_grounding(engine, retriever: HybridRetriever, emails: list[Email],
                      category: str, avoid: list[dict], used_anchors: set | None = None,
                      k_retrieve: int = 40, k_judge: int = 12, seen: list[dict] | None = None) -> dict:
    """Gen-4 proposal: gen ABSTRACT topic -> HyDE -> retrieve -> fit-judge, then return the abstract
    secret together with the fit-judge's ranked anchor candidates (pick, then runner-up). No
    `specialize`: the secret stays abstract; the anchor is only a real CARRIER (a real document /
    company / matter + era) that the downstream Step-2 plot is freely built around. The plot+judge
    is the real gate, so there is no separate Step-1 CHECK here.

    status in {grounded, dup, gen_error, hyde_error, none}. On `grounded`, `anchors` is an ordered
    list of Email objects to try (best first) — the runner walks them until the plot passes."""
    seen = avoid if seen is None else seen         # rejects dedup, but only KEPT secrets are shown
    topic = gen_topic(engine, category, avoid)
    if not topic:
        return {"status": "gen_error", "topic": None}
    if is_duplicate(topic, seen):
        return {"status": "dup", "topic": topic}

    hyde = gen_hyde(engine, topic)
    queries = list(hyde) + [topic.get("true_fact", ""), topic.get("false_belief", ""), topic.get("secret", "")]
    if not hyde and not any(tokenize(q) for q in queries):
        return {"status": "hyde_error", "topic": topic}

    ranked = retriever.retrieve(queries, k=k_retrieve)
    # Used anchors are NOT excluded here — the judge sees every candidate, so a genuinely best-fit
    # anchor can still be picked even if another topic already used it. Anti-collision is a soft
    # preference applied to the pick below, not a hard filter on what the judge may see.
    cand_emails, seen = [], set()
    for i, _ in ranked:
        e = emails[i]
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
    picks: list[Email] = []
    for key in ("pick", "runner_up"):
        v = verdict.get(key)
        if isinstance(v, int) and 0 <= v < len(emails) and emails[v] not in picks:
            picks.append(emails[v])
    picks = picks or cand_emails[:1]    # judge gave nothing usable — fall back to top retrieval
    # Soft anti-collision: prefer an anchor not already spent, but a duplicate is fine when it is the
    # genuine best fit — each eval item excises its own anchor, so sharing one never crosses answer keys.
    fresh = [e for e in picks if not (used_anchors and e.message_id in used_anchors)]
    order = fresh or picks
    return {"status": "grounded", "topic": topic, "hyde": hyde,
            "verdict": verdict, "anchors": order}
