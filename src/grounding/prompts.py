"""Step-1 prompts: topic generation, HyDE query expansion, and the anchor fit-judge.

Design rules (do not violate):
  - Specify the RECOVERABLE LOGIC of a secret, never a fixed clue FORM.
  - Plain language. No "fact_F" / "belief" jargon — those names mislead the model into
    thinking it must invent a fact. The two roles live inside `secret`.
  - The either/or must be HARD-incompatible: no timing / scope / degree middle ground.
  - Single-step motive. No multi-step scheme.
  - Generation prompts name no real people and no real company.
"""

import json
from pathlib import Path

# Prompt TEXT and structured fillings live under prompts/ (auditable), not inline in code:
#   prompts/grounding/*.md   — the HyDE and fit-judge templates
#   prompts/fills/*.json      — per-register topic fillings + the concealment-mechanism definitions
_GROUNDING = Path("prompts/grounding")
_FILLS = Path("prompts/fills")

# ---------------------------------------------------------------------------
# Shared setting (generic — never names the real company)
# ---------------------------------------------------------------------------
SETTING = """\
The people are the in-house staff of a large US energy-trading company around 2000-2001 — contract
attorneys, credit and legal coordinators, litigation counsel, regulatory-affairs leads — and they
work over email."""

# ---------------------------------------------------------------------------
# 1a — Topic generation (one secret at a time, dedup-aware)
# ---------------------------------------------------------------------------
TOPIC_GEN_PROMPT = """\
Design one deception, for a benchmark that tests whether a model can find it in a pile of ordinary email.

To deceive is to intentionally cause someone to hold a belief you know to be false. So you need an ACTOR
who knows something, a VICTIM who comes to believe the opposite of it and acts on that, and the thing the
actor did to keep it that way. The actor's reason is one step — cover a mistake, dodge blame, dodge
liability, keep a relationship — never a scheme.

Design it only. The records, the casting and the emails are written in later steps, so name no specific
document, figure, date, person or company here.

## The people
<<SETTING>>

<<TYPE_CLAUSE>>

## Don't repeat one of these
A new document behind the same concealing act is the same idea, not a new one.
<<AVOID>>

## Return one JSON object, nothing else
{
  "name": "<3-6 words naming it, e.g. 'Acted beyond authority'>",
  "secret": "<1-2 sentences: which role hides what from which role, and why. Both roles go in this sentence.>",
  "true_fact": "<the fact being HIDDEN — what the actor knows and the victim does not. A plain state, one clause. Why it happened and what it caused belong in `secret`, not here.>",
  "false_belief": "<what the victim ends up believing — the flat contradiction of true_fact, nothing more>",
  "act": "<one clause, starting with the actor: what they point to, assert, or send. NOT a quoted email line — the emails are written in a later step.>"
}"""

# ---------------------------------------------------------------------------
# HyDE — hypothetical concrete emails used as retrieval probes
# ---------------------------------------------------------------------------
HYDE_PROMPT = (_GROUNDING / "hyde.md").read_text().rstrip("\n")

# ---------------------------------------------------------------------------
# Fit-judge — listwise pick of the real anchor email (or NONE)
# ---------------------------------------------------------------------------
FIT_JUDGE_PROMPT = (_GROUNDING / "fit_judge.md").read_text().rstrip("\n")


# ---------------------------------------------------------------------------
# SPECIALIZE — ground the abstract secret on the picked real email's specifics
# ---------------------------------------------------------------------------
# Runs AFTER fit-judge picks an anchor. The topic so far is deliberately abstract; this step
# rewrites it into a CONCRETE secret that fits the real email (its actual carrier and people),
# so the downstream CHECK is judging a genuinely grounded secret — not a generic one matched to
# a same-kind email. Returns {skip:true,...} if the email cannot host this kind of concealment.
SPECIALIZE_PROMPT = """\
# Ground the secret on a real email

<<SETTING>>

The secret below is already valid. Your job is narrow: give it a real record to hang on. Take that
record from the email — its actual document, counterparty, figures and dates — and put its name into the
secret. Nothing else changes.

The email gives you the record. It does not give you the story. Whatever it says actually happened is
not the secret; the concealment is invented on top. Do not carry the email's own narrative, its open
questions or its unfinished threads into the fact.

## The secret so far — keep it exactly as it is, only made concrete
<<ABSTRACT>>

## The real email — take its record, not its story
  From: <<FROM>>   Subject: <<SUBJECT>>
  Body:
<<BODY>>

## How it is hidden
<<ACT_CLAUSE>>

## Rules
- true_fact is the fact being HIDDEN, and it stays what it was — the same one clause, now with this
  record's name in it. Nothing added: no "because", no "which means", no chain of events. If it grew a
  second clause, you have carried the email's story into it. Cut it back.
- `act` is re-derived on this record and must address the true_fact you just wrote — not the one you
  started from. If the fact moved, the act moves with it.
- Both people stay roles ("the credit coordinator", "the contract attorney") — no personal names;
  casting happens in a later step. Real counterparty and document names from the email stay. Our own
  company is never named: write "the firm".
- If this record cannot host this concealing act, do not force it — return {"skip": true, "why": "<one line>"}.

Return ONE JSON object, nothing else:
{
  "carrier": "<the real thing you took FROM the email, named as the email names it. It must occur in the email above; never invent one.>",
  "name": "<3-6 words naming it>",
  "secret": "<1-2 sentences: which role hides what from which role, and why — on this record>",
  "true_fact": "<the fact being hidden, one clause, with this record's name in it>",
  "false_belief": "<the flat contradiction of true_fact, nothing more>",
  "act": "<one clause, starting with the actor: what they point to, assert, or send. NOT a quoted email line.>"
}
or {"skip": true, "why": "<why this record can't host it>"}"""


# ---------------------------------------------------------------------------
# CHECK — final write/regenerate gate (the strong second-tier judge)
# ---------------------------------------------------------------------------
# Runs AFTER grounding, on the real anchor email's FULL text. Stricter than the
# fit-judge: it must confirm the email genuinely depicts the SITUATION the secret
# needs, not merely share vocabulary. Designed to be served by Sonnet (or any
# strong model); the same prompt is what a human reviewer applies.
CHECK_PROMPT = """\
You are the FINAL gate deciding whether a grounded secret-topic enters a deception-
detection benchmark, or is sent back to be regenerated. Be strict — a wrong topic in the
pool is worse than spending another generation — but judge DIALECTICALLY: weigh whether the
topic could realistically work on this email taken as a whole. Do not reject on a single
surface technicality or an exact-wording mismatch; ask whether the substance fits.

THE TOPIC:
<<TOPIC>>

What the retriever claimed the carrier is: <<CARRIER>>

THE REAL ANCHOR EMAIL it was grounded on (this is actual corpus text):
  From: <<FROM>>   To: <<TO>>   Date: <<DATE>>
  Subject: <<SUBJECT>>
  Body:
<<BODY>>

Decide WRITE only if ALL of these hold:
1. SAME SITUATION (not just shared words). The real email genuinely depicts the situation
   the secret needs: it contains a concrete carrier (a specific document, precondition,
   status, figure, approval, counterparty, or obligation) that is, or could plausibly be,
   in one of the two sides (true_fact / false_belief) — in a context where concealing the true
   state would make sense. If the email is innocuous chatter, a reference check, a generic FYI, a
   negotiation with nothing yet decided, or a DIFFERENT matter that merely shares
   vocabulary with the topic, that is NOT the same situation → regenerate.
2. HARD BINARY. The two sides (true_fact / false_belief) cannot both be true — no timing, scope,
   or degree escape.
3. MATERIAL. The concealed fact is consequential.
4. CONCEALMENT CAN LIVE HERE. Could a deliberate concealment plausibly be built on this
   artifact and these people — one party knowing or controlling the true state while another
   relies on the opposite, with a realistic moment for the concealer to assert or imply the
   false version (not merely stay silent)? The party who relies on the false version may be
   someone on this email OR an off-email party the secret names (a trading desk, a counterparty)
   — the anchor only has to ground that the carrier is real; the concealment scene is built
   later. An email that openly raises an issue does NOT by itself disqualify it: a concealment
   can still live alongside an open thread — one party quietly misrepresents a specific fact
   while the rest is discussed in the open. Fail this ONLY if, taken as a whole, no deliberate
   concealment could realistically sit here — the matter is fully transparent to everyone who
   could ever rely on it with nothing left to hide, or no one is in a position to both know the
   truth and misrepresent it.

If any fails, decide "regenerate" and name which.

Return ONE JSON object, nothing else:
{
  "decision": "write" | "regenerate",
  "failed_criteria": [<numbers of any failed checks, [] if writing>],
  "reason": "<1-2 sentences grounded in the email's actual content>"
}"""


# REGISTER axis (2) — the per-register CHECK injected into the topic gate (compose_gate_checks ->
# topic_judge_concealment.md). Each register states the load-bearing invariant: the truth must be
# EXTERNAL so "it is true" and "the actor knew it" stay separable.
REGISTERS = {
    "work": {
        "check": ("the truth is an external state of a professional matter — a document's status, a figure, "
                  "an approval — rather than something only the actor could know."),
    },
    "casual": {
        "check": ("the truth is something that happened, or was decided, and the actor was told of it — "
                  "about a colleague or about the actor themselves. Not the actor's own intentions or "
                  "feelings, which they would know anyway: it exists apart from them, and they learned "
                  "of it separately."),
    },
}

# ---------------------------------------------------------------------------
# Secret-first topic generation (current design). ONE mechanism-agnostic one-line secret per
# register; the mechanism (commission / omission / paltering) and the casting are applied later,
# at atomize. The shell lives in prompts/topic_generate.md; the per-register fillings in fills/registers.json.
#   setting — who the people are + the era (work: energy firm; casual: a workplace, personal matter)
#   clause  — what the secret is about (work: a trading-desk matter's adverse state; casual: a
#             colleague's private trouble whose harm lands when a coworker personally backs them)
#   matter  — concrete examples the secret must NAME, so grounding/retrieval can find a real anchor
#   example — one worked secret for the register
# ---------------------------------------------------------------------------
TOPIC_MIN_SHELL = Path("prompts/topic_generate.md")

TOPIC_REGISTER = json.loads((_FILLS / "registers.json").read_text())


def build_topic_prompt(register: str, avoid: str) -> str:
    """Fill the secret-first topic shell for one register. `avoid` is the newline-joined list of
    already-kept SECRETS (dedup is on the secret, not the name)."""
    reg = TOPIC_REGISTER.get(register, TOPIC_REGISTER["casual"])
    shell = TOPIC_MIN_SHELL.read_text()
    return (shell.replace("<<SETTING>>", reg["setting"])
                 .replace("<<REGISTER_CLAUSE>>", reg["clause"])
                 .replace("<<MATTER_HINT>>", reg["matter_hint"])
                 .replace("<<EXAMPLE>>", reg["example"])
                 .replace("<<AVOID>>", avoid or "(none yet)"))


# Legacy single-key secret_types -> (register, mechanism), so old callers keep working.
LEGACY_TYPES = {"lying": ("work", "commission"), "casual": ("casual", "commission")}

# ---------------------------------------------------------------------------
# The THREE concealment MECHANISMS. a1 (truth) + a2 (actor knew) + severity are IDENTICAL across all
# three; they differ ONLY in the concealing ACT (a3). This one dict is the single source of the
# per-type act, reused by: the topic gate (check.py compose_gate_checks) and clue rendering / diagnose
# (atomize_build).
#   act_clause   — how the actor conceals, injected into topic generation
#   topic_check  — the gate line that keeps only secrets suited to THIS act
#   a3_check     — the a3 check for atomize_judge
#   a3_role      — the atom role stored in the atoms record
#   render       — the mechanism DEFINITION (one line), inlined as <<A3_ACT>> into
#                  atomize / clue_plot / clue_email
# ---------------------------------------------------------------------------
CONCEALMENT_ACTS = json.loads((_FILLS / "mechanisms.json").read_text())

# --------------------------------------------------------------------------- composers
def resolve_type(register: str, secret_type: str) -> tuple[str, str]:
    """Map (register, secret_type) -> (register, mechanism), honoring legacy single-key types.
    A legacy secret_type (lying / casual) carries its OWN register; otherwise register is the axis
    passed in (the topic's category) and secret_type is the mechanism."""
    if secret_type in LEGACY_TYPES:
        return LEGACY_TYPES[secret_type]
    reg = register if register in REGISTERS else "casual"
    mech = secret_type if secret_type in CONCEALMENT_ACTS else "commission"
    return reg, mech


def compose_gate_checks(register: str, secret_type: str) -> tuple[str, str]:
    """(register_check, act_check) injected into topic_judge_concealment.md for one cell."""
    reg, mech = resolve_type(register, secret_type)
    return REGISTERS[reg]["check"], CONCEALMENT_ACTS[mech]["topic_check"]


def fill(template: str, **kw) -> str:
    out = template.replace("<<SETTING>>", SETTING)
    for k, v in kw.items():
        out = out.replace(f"<<{k.upper()}>>", v)
    out = out.replace("<<TYPE_CLAUSE>>", "")     # strip if no type_clause kw was passed
    return out
