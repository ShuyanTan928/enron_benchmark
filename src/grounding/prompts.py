"""Step-1 prompts: topic generation, HyDE query expansion, and the anchor fit-judge.

Design rules (do not violate):
  - Specify the RECOVERABLE LOGIC of a secret, never a fixed clue FORM.
  - Plain language. No "fact_F" / "belief" jargon — those names mislead the model into
    thinking it must invent a fact. The two roles live inside `secret`.
  - The either/or must be HARD-incompatible: no timing / scope / degree middle ground.
  - Single-step motive. No multi-step scheme.
  - Generation prompts name no real people and no real company.
"""

from pathlib import Path

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
HYDE_PROMPT = """\
<<SETTING>>

Here is an abstract secret:
<<TOPIC>>

Write FOUR short, realistic emails (2-4 sentences each) of the kind that would actually
sit in one of these mailboxes and, read together, would let someone infer the true_fact vs
false_belief above. Make them concrete: name a plausible deal / document / approval /
counterparty / figure and treat the hidden fact as a mundane work matter. Spread them so that
some lean to the true side and some to the believed side, and at least one just handles the
carrier itself.

These are SEARCH PROBES to find a real matching email — not the benchmark. Use no real
person names and no real company name. Do not explain; output only the emails.

Return a JSON array of exactly four strings:
["<email 1 body>", "<email 2 body>", "<email 3 body>", "<email 4 body>"]"""

# ---------------------------------------------------------------------------
# Fit-judge — listwise pick of the real anchor email (or NONE)
# ---------------------------------------------------------------------------
FIT_JUDGE_PROMPT = """\
You are grounding an abstract secret on a REAL email. Below is the secret and a numbered
list of candidate real emails retrieved from the corpus.

SECRET:
<<TOPIC>>

CANDIDATE EMAILS:
<<CANDIDATES>>

Pick the candidate that best fits as the SETTING for this secret — the email whose subject
matter is the SAME KIND of thing the secret is about (the same kind of document, approval,
status, figure, counterparty, or obligation), naming a concrete, material carrier on which
the "one party conceals X, another relies on the opposite" dynamic could realistically be built.

The email does NOT need to say anything about the secret, or show which side is true. It is enough
that it names a real record of the right kind, one the secret could attach to — the concealment is
invented in the NEXT step, not read off this email. An email that merely discusses, FYIs, or raises
the matter is perfectly fine.

Reject a candidate only when it is the WRONG KIND of matter: it shares vocabulary but the
carrier is a different kind of thing than the secret concerns (e.g. the secret is about a
counterparty's CREDIT approval but the email is about an unrelated product-type approval —
that does NOT count just because both are "approved vs not").

Prefer the best same-kind carrier. Return "pick": null ONLY if NO candidate is even the right
kind of matter — not merely because no email spells the secret out.

Return ONE JSON object, nothing else:
{
  "pick": <id number of the chosen email, or null>,
  "carrier": "<the concrete thing in that email, and the yes/no about it the secret could turn on, e.g. 'the counterparty's letter of credit: in place vs waived'>",
  "side_shown": "<which side (true_fact / false_belief) this email leans toward, or 'unstated'>",
  "why": "<1-2 sentences: why this email fits as the setting; if null, why NO candidate is the right kind>",
  "runner_up": <id of a second-best candidate, or null>
}"""


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
# at atomize. The shell lives in prompts/topic_generate_min.md; the per-register fillings live here.
#   setting — who the people are + the era (work: energy firm; casual: a workplace, personal matter)
#   clause  — what the secret is about (work: a trading-desk matter's adverse state; casual: a
#             colleague's private trouble whose harm lands when a coworker personally backs them)
#   matter  — concrete examples the secret must NAME, so grounding/retrieval can find a real anchor
#   example — one worked secret for the register
# ---------------------------------------------------------------------------
TOPIC_MIN_SHELL = Path("prompts/topic_generate_min.md")

TOPIC_REGISTER = {
    "work": {
        "setting": "The setting is a US energy-trading company around 2000-2001.",
        "clause": ("A trading-desk matter in an adverse state — expired, rejected, terminated, breached, "
                   "withdrawn, curtailed, etc. — that holds whether or not anyone has looked, and costs the "
                   "firm real money or standing once someone acts on the opposite."),
        "matter_hint": "naming the concrete matter (a deal, a limit, a filing, or a standing status — a filed record or a stated fact, either) so it's findable later",
        "example": ('{"name": "Expired credit limit hidden",\n'
                    ' "secret": "A counterparty\'s approved credit limit has expired and was never '
                    'renewed, kept quiet so trades keep clearing against a line that no longer exists."}'),
    },
    "casual": {
        "setting": ("The setting is a US workplace around 2000-2001 — coworkers who know each other "
                    "through the office, over email. The matter is personal, not company business."),
        "clause": ("A private trouble serious enough to sink someone if it came out — e.g. a crime charge, "
                   "an unpayable debt, a revoked licence, a falsified credential, a firing for cause, an "
                   "affair. It's about a colleague, or the actor themselves — either."),
        "matter_hint": "naming what it's about (e.g. a fraud conviction, an unpayable debt, an affair, a firing for cause)",
        "example": ('{"name": "Hidden fraud conviction",\n'
                    ' "secret": "A colleague has an undisclosed felony fraud conviction on their record, '
                    'kept quiet so a coworker keeps vouching for them to a lender."}'),
    },
}


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
CONCEALMENT_ACTS = {
    "commission": {
        "label": "LYING BY COMMISSION",
        "act_clause": ("Lying by commission is the active use of false statements. In `act`, name what the actor "
                       "asserts to the victim — false, given the hidden truth. An assurance that it is fine, or a "
                       "denial that anything is wrong; whichever the matter invites."),
        "topic_check": ("`act` names what the actor asserts to the victim, and it is FALSE given the true_fact, with no "
                        "honest reading. FAIL if it is true-but-misleading (that is paltering), if it is silence (that "
                        "is omission), if it is merely hedged, or if it states the truth."),
        "a3_role": "false_statement",
        "a3_check": ("a3 is a quotable sentence the actor asserts to the victim, FALSE given a1, with no honest "
                     "reading. FAIL if it is silence, a hedge, a literally-true line, or if it states the truth."),
        "render": "one plain sentence the actor says to the victim, false given the truth.",
    },
    "omission": {
        "label": "LYING BY OMISSION",
        # Faithful to Rogers et al.: no duty-to-disclose requirement. What makes the omission observable is
        # not a duty but RELEVANCE: the actor's own message covers the matter, and the fact is missing from it.
        "act_clause": ("Lying by omission is the passive omission of relevant information, rather than actively "
                       "misleading. The actor writes to the victim about the matter — a status line, a handoff, an "
                       "answer — and the fact simply is not in it. Nothing false is said, nothing misleading. In "
                       "`act`, name the message the actor sends and what it covers, with the fact missing.\n"
                       "It reads as concealment only because the actor's own message was where the fact belonged."),
        "topic_check": ("`act` is a message the actor sends the victim about this very matter, in which the true_fact "
                        "is the relevant thing left out — everything said is true and not misleading, and the fact's "
                        "absence is visible because this message is where it belonged. FAIL if the actor says anything "
                        "false (commission) or true-but-misleading (paltering), if the actor never communicates with "
                        "the victim about the matter at all (then there is no observable act), or if the fact is not "
                        "relevant to what the message covers."),
        "a3_role": "withheld_disclosure",
        "a3_check": ("a3 is the actor's own message to the victim about the matter, with a1 the relevant fact left "
                     "out — nothing false, nothing misleading said. FAIL if the actor asserts anything false "
                     "(commission) or true-but-misleading (paltering), if the truth is stated, or if there is no "
                     "message from the actor at all — bare silence leaves no act to observe."),
        "render": "the actor's own message to the victim about the matter, with the fact left out — it covers other points but says nothing about the fact's own dimension, not even a status on it (any word there asserts or leans, and it stops being omission).",
    },
    "paltering": {
        "label": "PALTERING",
        # The two lever tests below just make the definition's two halves checkable: "truthful statements"
        # (TRUE ALONGSIDE) and "convey a misleading impression" (POINTS THE WRONG WAY). SAME DOMAIN is ours,
        # not the paper's: without it the writer is forced to add a false word to land the deception.
        "act_clause": ("Paltering is the active use of truthful statements to convey a misleading impression. In `act`, "
                       "say what the actor points the victim to — SOMETHING ELSE that happens to be true, never "
                       "true_fact itself, which is the thing being hidden. The victim draws the false conclusion from "
                       "it; the actor never states that conclusion.\n"
                       "What the actor points to must still hold with true_fact in force, and it must actually mislead "
                       "— so not something true_fact already implies (a failed exam was certainly sat, so citing the "
                       "sitting misleads no one). What works is a different record, bearing on the same question, that "
                       "really is in good order: a suspended licence behind a current registration."),
        "topic_check": ("`act` names what the actor points the victim to — the LEVER. It is something other than "
                        "true_fact, it holds even with true_fact in force, and a reasonable person hearing it lands on "
                        "the false side. FAIL only if the lever is missing, if it is actually false given true_fact "
                        "(that is commission), if true_fact already implies it so it misleads no one, or if it bears on "
                        "some other question entirely and reassures only by what it leaves unsaid (that is omission)."),
        "a3_role": "misleading_truth",
        "a3_check": ("a3 is ONE literally TRUE sentence the actor says to the victim: still true given a1, and it leads "
                     "the victim to the false belief. FAIL only if it says something false (commission), if there is no "
                     "statement at all (omission), if it states the truth, or if a1 already implies it so it misleads "
                     "no one."),
        "render": ("one true sentence on the SAME matter as the hidden fact: the actor confirms that the "
               "matter's visible side is going fine — which really is true — so the victim assumes the "
               "hidden problem underneath isn't there. it stays on the matter the victim is deciding, "
               "never a different topic, and never says the hidden fact or the conclusion.\n"
               "  hidden: the storage contract is terminated -> a3: 'the winter packages are all booked "
               "and on schedule' (true; the sales really are booked).\n"
               "  hidden: their licence is suspended -> a3: points to their current firm registration (true).\n"
               "  hidden: the netting agreement lapsed -> a3: 'the exposure figures are on the books and "
               "in the committee pack' (true; the figures really are there)."),
    },
}

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
