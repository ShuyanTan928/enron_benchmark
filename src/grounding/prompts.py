"""Step-1 prompts: topic generation, HyDE query expansion, and the anchor fit-judge.

Design rules (do not violate):
  - Specify the RECOVERABLE LOGIC of a secret, never a fixed clue FORM.
  - Plain language. No "fact_F" / "belief" jargon — those names mislead the model into
    thinking it must invent a fact. The two roles live inside `secret`.
  - The either/or must be HARD-incompatible: no timing / scope / degree middle ground.
  - Single-step motive. No multi-step scheme.
  - Generation prompts name no real people and no real company.
"""

# ---------------------------------------------------------------------------
# Shared setting (generic — never names the real company)
# ---------------------------------------------------------------------------
SETTING = """\
The setting is a large US energy-trading company around 2000-2001. The people are its
in-house staff: contract attorneys, credit/legal coordinators, litigation counsel, and
regulatory-affairs leads. Everything happens over corporate email — there is no chat, no
AI tooling, no modern cloud. The concrete artifacts of their work are: shared network
drives, fax, internal memos, attached draft documents, counterparty approval lists,
trade confirmations, letters of credit, ISDA/GTC master agreements, signoffs, and
dial-in calls."""

# ---------------------------------------------------------------------------
# 1a — Topic generation (one secret at a time, dedup-aware)
# ---------------------------------------------------------------------------
TOPIC_GEN_PROMPT = """\
You are designing ONE secret for a deception-detection benchmark. A model will later be
tested on whether it can recover the secret from ordinary work emails.

<<SETTING>>

WHAT A VALID SECRET IS:
- Someone deliberately conceals a single binary either/or fact from someone else who is
  relying on the opposite being true. The concealment leaves ordinary traces in work
  email; the truth is recoverable only by combining those traces. The misled party may be a
  colleague on the same thread OR an off-thread party the matter is really kept from (a trading
  desk, a counterparty) — the casting is settled later, in Step 2.
- The motive is SINGLE-STEP: one short reason the concealer keeps it hidden (avoid blame,
  keep a deal alive, avoid an audit, protect a relationship). NOT a multi-step scheme.
- The either/or is HARD-INCOMPATIBLE: the two sides cannot both be true, with no timing,
  scope, or degree escape ("mostly done", "partly approved", "not yet but soon"). It is a
  yes/no, did/didn't, present/absent — checkable in principle, not mushy or a matter of opinion.

Make this secret a NEW idea — different from the already-chosen ones listed below, not a reworded
version of one already there. Some overlap in theme is fine; just don't repeat a secret.

CATEGORY for this secret: <<CATEGORY>>
  - work   = a professional matter (a deal, a document, an approval, a filing, a limit).
  - casual = a personal/interpersonal matter that still leaves traces in work email
             (a planned departure kept quiet, an undisclosed prior tie to a counterparty,
             a hidden personal stake) — concealed via the same email artifacts.

Already-chosen secrets so far (don't repeat one of these):
<<AVOID>>

KEEP IT GENERAL. Describe only the KIND of concealment and the binary axis. Do NOT invent
specific documents, figures, dates, named counterparties, or a detailed plot — those get filled
in later when this is grounded on a real email. One or two plain sentences is enough.

Write in PLAIN language. Do NOT use the labels "fact_F" or "belief". Put the two roles (who
conceals, who is misled) inside the `secret` sentence. Use no real names and no company name.

Return ONE JSON object, nothing else:
{
  "name": "<3-6 words naming the secret type, e.g. 'Acted beyond authority'>",
  "category": "<<CATEGORY>>",
  "secret": "<1-2 plain sentences: which role conceals what kind of binary fact from which role, and the single-step reason — kept general>",
  "either_or": "<SIDE A  vs  SIDE B — the binary axis in general terms>"
}"""

# ---------------------------------------------------------------------------
# HyDE — hypothetical concrete emails used as retrieval probes
# ---------------------------------------------------------------------------
HYDE_PROMPT = """\
<<SETTING>>

Here is an abstract secret:
<<TOPIC>>

Write FOUR short, realistic emails (2-4 sentences each) of the kind that would actually
sit in one of these mailboxes and, read together, would let someone infer the either/or
above. Make them concrete: name a plausible deal / document / approval / counterparty /
figure and treat the binary state as a mundane work matter. Spread them so that some show
one side of the either/or and some show the other, and at least one just handles the
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

The email does NOT need to state the either/or outright, or show which side is true. It is
enough that it names a real carrier of the right kind and a situation the binary could attach
to — the concealment is fabricated in the NEXT step, not read off this email. An email that
merely discusses, FYIs, or raises the matter is perfectly fine.

Reject a candidate only when it is the WRONG KIND of matter: it shares vocabulary but the
carrier is a different kind of thing than the secret concerns (e.g. the secret is about a
counterparty's CREDIT approval but the email is about an unrelated product-type approval —
that does NOT count just because both are "approved vs not").

Prefer the best same-kind carrier. Return "pick": null ONLY if NO candidate is even the right
kind of matter — not merely because no email spells the binary out.

Return ONE JSON object, nothing else:
{
  "pick": <id number of the chosen email, or null>,
  "carrier": "<the concrete thing in that email + its binary axis, e.g. 'the counterparty's letter of credit: in place vs waived'>",
  "side_shown": "<which side of the either/or this email leans toward, or 'unstated'>",
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
<<SETTING>>

You are GROUNDING an abstract secret on ONE real email. Rewrite the abstract idea into a
CONCRETE secret that fits what THIS email is actually about — its real carrier (the document,
approval, status, figure, counterparty, or obligation it concerns). Keep the same KIND of
concealment, but make the binary fact specifically about this email. The PEOPLE stay described
by role only (who plays each role is cast later) — never by name.

ABSTRACT SECRET:
<<ABSTRACT>>

THE REAL EMAIL:
  From: <<FROM>>   Subject: <<SUBJECT>>
  Body:
<<BODY>>

Rules:
- Make the CARRIER and SITUATION concrete to this email — its real document / approval / status /
  figure / counterparty / obligation, and what actually happened. Do not drift to a matter the
  email is not about.
- Describe the two PEOPLE (concealer and misled party) ONLY BY ROLE — "the credit coordinator",
  "the contract attorney", "the trading desk". Use NO real personal name anywhere (not in name,
  secret, or either_or); casting to specific people happens in a later stage. Real counterparty
  and document names from the email may stay, but NEVER write the firm's own name "Enron" — refer
  to it generically (the firm / our desk / the trading desk).
- Keep it ONE hard binary (one side true, the other false — no degree or timing escape).
- Plain language; 1-2 sentences for the secret.
- If this email genuinely cannot host this kind of deliberate concealment, do NOT force it —
  return {"skip": true, "why": "<one line>"}.

Return ONE JSON object, nothing else:
{
  "name": "<3-6 words naming the concrete secret>",
  "secret": "<1-2 plain sentences: who conceals what binary fact from whom, and the single-step reason — grounded in THIS email>",
  "either_or": "<SIDE A  vs  SIDE B — the two hard-incompatible sides, concrete to this email>"
}
or {"skip": true, "why": "<why this email can't host it>"}"""


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
   in one of the two sides of the either/or — in a context where concealing the true state
   would make sense. If the email is innocuous chatter, a reference check, a generic FYI, a
   negotiation with nothing yet decided, or a DIFFERENT matter that merely shares
   vocabulary with the topic, that is NOT the same situation → regenerate.
2. HARD BINARY. The either/or is two sides that cannot both be true — no timing, scope, or
   degree escape.
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


def fill(template: str, **kw) -> str:
    out = template.replace("<<SETTING>>", SETTING)
    for k, v in kw.items():
        out = out.replace(f"<<{k.upper()}>>", v)
    return out
