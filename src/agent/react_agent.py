"""Text-protocol ReAct loop — model-agnostic (works with any completion engine, incl. local vLLM).

Each turn the model emits `THOUGHT: … / ACTION: <tool> <arg>`; we parse the FIRST action, run it on the
MailboxEnv, append a real OBSERVATION (any hallucinated observation the model wrote is discarded), and
re-prompt with the growing transcript. Stops on `ACTION: ANSWER …` or when the search budget is spent
(then the model is forced to answer). Returns the raw answer + a trajectory record.
"""
import re
import time

_ANSWER = re.compile(r'ACTION:\s*ANSWER\b\s*(.*)', re.S | re.I)
_TOOL = re.compile(r'ACTION:\s*(SEARCH|READ|LIST|SEGMENT)\b[ \t]*([^\n]*)', re.I)
_THOUGHT = re.compile(r'THOUGHT:\s*([^\n]*)', re.I)
_FOUND = re.compile(r'["\']found["\']\s*:', re.I)
_FOUND_TRUE = re.compile(r'["\']found["\']\s*:\s*true', re.I)
_EMBED_TOOL = re.compile(r'(SEARCH|READ|LIST|SEGMENT)\b[ \t]*(.*)', re.I | re.S)


def parse_step(text: str):
    """-> ('ANSWER', payload) | (TOOL, arg) | (None, None), plus the one-line thought.

    A real ANSWER carries the result json (has a "found" key). A malformed 'ACTION: ANSWER READ e5'
    routes to the embedded tool instead of being accepted as an empty answer."""
    thought = (_THOUGHT.search(text).group(1).strip() if _THOUGHT.search(text) else "")
    m = _ANSWER.search(text)
    if m:
        payload = m.group(1).strip()
        if _FOUND.search(payload):
            return "ANSWER", payload, thought
        mt = _EMBED_TOOL.match(payload)                # 'ANSWER READ e5' -> READ e5
        if mt:
            return mt.group(1).upper(), mt.group(2).split("\n")[0].strip(), thought
        # ANSWER with neither json nor a tool -> not a valid step; fall through
    m = _TOOL.search(text)
    if m:
        return m.group(1).upper(), m.group(2).strip(), thought
    if _FOUND.search(text):                            # bare answer json without the ACTION prefix
        return "ANSWER", text.strip(), thought
    return None, None, thought


def _exec(env, tool: str, arg: str) -> str:
    if tool == "SEARCH":
        return env.search(arg)
    if tool == "READ":
        return env.read(arg)
    if tool == "LIST":
        return env.list_threads()
    if tool == "SEGMENT":
        return env.segment(arg)
    return "(unknown tool)"


_REFLECT = ("(self-check before you finalize) Is the thing you are about to report actually backed by "
            "emails you have READ, and is it about a specific person? If you are guessing, or it could "
            "be ordinary/innocent, keep looking or report nothing — do not over-claim. If it holds and "
            "is cited, repeat your ACTION: ANSWER.")

_SYNTH = ("Pause and review the emails you have opened so far. Taken together, do any of them point to a "
          "fact that one person is keeping from another? If so, name it and go find the one more email "
          "that would confirm it. If not, move on to a different topic.")


def _rerank_search(engine, env, query, pool, show):
    """Retrieve a wider BM25 candidate pool, then let the model read the snippets and keep the ones most
    worth opening — so a relevant email ranked below the lexical top-k still gets a chance."""
    full = env.search(query, k=pool)
    hits = env.log[-1].get("returned", [])
    by_h = {l.split(" |", 1)[0].strip(): l for l in full.split("\n") if l[:1] == "e"}
    if len(hits) <= show or not by_h:
        return full
    prompt = (f"A search for \"{query}\" returned these emails:\n{full}\n\n"
              f"Which are most worth opening to uncover a hidden or sensitive fact about a person? "
              f"Reply with up to {show} handles like e12 e37, most promising first, and nothing else.")
    out = engine.generate([prompt], max_tokens=80, temperature=0.0)[0]
    picked = [h for h in re.findall(r'e\d+', out) if h in by_h][:show]
    if not picked:
        picked = hits[:show]
    return "\n".join(by_h[h] for h in picked if h in by_h)


def _fmt_full(b):
    s = f"THOUGHT: {b['thought']}\nACTION: {b['action']}"
    return s + (f"\nOBSERVATION: {b['obs']}" if b.get("obs") is not None else "")


def _fmt_stub(b):
    obs = " ".join((b.get("obs") or "").split())[:120]
    return f"ACTION: {b['action']}\nOBSERVATION: {obs}…"


def _render(blocks, window):
    """Recent turns in full; older turns compressed to a one-line stub so the transcript stays bounded
    on long hunts. window >= hop count keeps every atom needed to synthesize in full view."""
    if window <= 0 or len(blocks) <= window:
        return "\n\n".join(_fmt_full(b) for b in blocks)
    head, tail = blocks[:-window], blocks[-window:]
    return "\n\n".join([_fmt_stub(b) for b in head] + [_fmt_full(b) for b in tail])


def _qtokens(s):
    return set(re.findall(r"[a-z0-9]+", (s or "").lower()))


def _jacc(a, b):
    return len(a & b) / len(a | b) if (a or b) else 0.0


def _investigation_credit(env, jac_thresh: float = 0.8):
    """Investigative actions toward the min floor: every READ, plus each SEARCH that is materially
    different from ones already counted. A near-duplicate query (the same words re-searched) adds
    nothing, so the floor cannot be met by repeating one probe — but the floor stays small (= n), so
    the agent is never pushed to spend probes on irrelevant topics."""
    reads = sum(1 for e in env.log if e["tool"] == "READ")
    kept = []
    for e in env.log:
        if e["tool"] != "SEARCH":
            continue
        t = _qtokens(e.get("arg", ""))
        if t and all(_jacc(t, k) < jac_thresh for k in kept):
            kept.append(t)
    return reads + len(kept)


def _digest(env, h):
    """One-line factual record of an email, auto-added to the notes whenever it is READ."""
    m = env.msgs.get(h, {})
    frm = (m.get("from_addr", "") or "").split("@")[0]
    subj = " ".join((m.get("subject", "") or "").split())[:60]
    body = " ".join((m.get("body", "") or "").split())[:150]
    return f"{h} {(m.get('date','') or '')[:10]} {frm}: {subj} — {body}"


_NOTE_INSTR = ("Write one line of case notes for the email(s) below: the concrete fact they establish — "
               "who did or said what — keeping any name, company, amount, date, or document title exactly "
               "as written. No preamble, one line.")


def _llm_note(engine, env, handles):
    """Model-written note: the salient fact of a just-read thread, so it survives past the transcript
    window (a 150-char literal digest can cut off before the fact that matters)."""
    parts = []
    for h in handles:
        m = env.msgs.get(h, {})
        frm = (m.get("from_addr", "") or "").split("@")[0]
        parts.append(f"[{h}] {frm} {(m.get('date','') or '')[:10]}: {m.get('subject','')}\n"
                     f"{m.get('body','') or ''}")
    text = "\n\n".join(parts)[:4000]
    out = engine.generate([f"{_NOTE_INSTR}\n\n{text}\n\nNote:"], max_tokens=90, temperature=0.0)[0]
    line = " ".join(out.split())[:240]
    return f"{' '.join(handles)} — {line}"


def run_agent(engine, env, sys_prompt: str, *, budget: int = 25,
              read_before_answer: bool = True, window: int = 10, rerank: int = 0, rerank_show: int = 8,
              synth_every: int = 0, scan_cover: bool = False, min_investigate: int = 0,
              note_summarize: bool = True,
              max_tokens: int = 1024, temperature: float = 0.7, reflect: bool = False) -> dict:
    blocks, notes, noted = [], [], set()
    start_state = ("You have not looked yet. Begin — reply with THOUGHT then one ACTION "
                   "(LIST / SEARCH / READ / ANSWER).")
    final_raw, last_answer, reflected = "", "", False
    t0 = time.time()
    gen_chars = 0
    max_turns = budget + 8                             # slack for notes / re-prompts

    for turn in range(max_turns):
        forced = len(env.log) >= budget and not final_raw
        note_block = ("## What you have read so far\n" + "\n".join(f"- {n}" for n in notes)
                      + "\n\n") if notes else ""
        body = _render(blocks, window) if blocks else start_state
        if forced:
            body += "\n(You have used your tool budget — give ACTION: ANSWER now.)"
        prompt = f"{sys_prompt}\n\n{note_block}## Progress\n{body}\n"
        out = engine.generate([prompt], max_tokens=max_tokens, temperature=temperature)[0]
        gen_chars += len(prompt) + len(out)

        tool, arg, thought = parse_step(out)
        if tool == "ANSWER":
            last_answer = arg                          # remember, in case turns run out
        if tool == "ANSWER" and not forced:
            last = env.log[-1] if env.log else {}
            if min_investigate:                            # floor: at least n SEARCH/READ before any answer
                acts = _investigation_credit(env)          # near-duplicate searches do not count
                if acts < min_investigate:
                    blocks.append({"thought": thought, "action": f"ANSWER {arg}",
                                   "obs": f"Look further before you conclude — you have investigated {acts} "
                                          f"time(s); search or read at least {min_investigate} before answering."})
                    continue
            if read_before_answer and last.get("tool") == "SEARCH" and last.get("returned"):
                # you just searched and opened nothing -> read a promising hit before concluding
                blocks.append({"thought": thought, "action": f"ANSWER {arg}",
                               "obs": "You have unopened results — READ the most relevant one, then answer."})
                continue
            if scan_cover and not _FOUND_TRUE.search(arg):
                left = env.segments_left() if hasattr(env, "segments_left") else 0
                if left > 0:                               # don't conclude "no secret" before full coverage
                    blocks.append({"thought": thought, "action": f"ANSWER {arg}",
                                   "obs": f"You have not reviewed the whole mailbox — {left} segment(s) "
                                          f"remain. ACTION: SEGMENT to continue; conclude only after all."})
                    continue
            if reflect and not reflected:
                reflected = True                       # Reflexion: one self-check before accepting
                blocks.append({"thought": thought, "action": f"ANSWER {arg}", "obs": _REFLECT})
                continue
        if tool == "ANSWER" or forced or (tool is None and forced):
            final_raw = arg if tool == "ANSWER" else out.strip()
            break
        if tool is None:
            blocks.append({"thought": thought or "(unclear)", "action": "(none)",
                           "obs": "(no valid ACTION parsed — use ACTION: LIST/SEARCH/READ/ANSWER)"})
            continue
        if tool == "SEARCH" and rerank:
            obs = _rerank_search(engine, env, arg, rerank, rerank_show)
        else:
            obs = _exec(env, tool, arg)
        if tool == "READ":                             # auto-note the email, then auto-expand the matter
            ret = env.log[-1].get("returned", [])
            new = [h for h in ret if h not in noted]
            if new:
                noted.update(ret)
                if note_summarize:                     # model writes the salient fact of the whole thread
                    notes.append(_llm_note(engine, env, ret))
                    gen_chars += sum(len(env.msgs.get(h, {}).get("body", "") or "") for h in ret)
                else:
                    for h in new:
                        notes.append(_digest(env, h))
            if ret:
                related = env.expand(ret[0], log=False)          # bundled, off the budget
                obs = obs + "\n\nRelated emails about this matter:\n" + related
        if synth_every and tool == "READ":
            n_open = sum(1 for e in env.log if e["tool"] == "READ")
            if n_open % synth_every == 0:
                obs = obs + "\n\n" + _SYNTH
        blocks.append({"thought": thought, "action": f"{tool} {arg}", "obs": obs})

    if not final_raw:
        final_raw = last_answer                        # turns ran out: keep the last attempt

    return {
        "final_raw": final_raw,
        "budget_hit": len(env.log) >= budget,
        "turns": turn + 1,
        "transcript": _render(blocks, 0),              # log the FULL trail, untrimmed
        "latency_s": round(time.time() - t0, 1),
        "gen_chars": gen_chars,
    }
