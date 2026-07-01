# Build the canonical SPEC of one concealment (lying)

A deception-detection benchmark hides one concealed fact inside ordinary work emails and tests
whether a model can recover it. Take the SECRET, ground it in the real ANCHOR email, and produce
the SPEC — the structured, indivisible facts the clue emails will later be written FROM. You are NOT
writing emails or a narrative here; you are producing the load-bearing facts and their specifics.

People are anonymous labels (Person A…J). Never name a real company; the firm is "[firm]".
Counterparties named in the anchor are real and stay.

## SECRET — the binary fact to plant
<<TOPIC>>

## ANCHOR — the real email this is grounded in (its matter, dates, counterparty, figures are real)
<<ANCHOR>>

## TEAM — the people you may cast
<<RELATIONSHIPS>>

## The model of a LYING concealment — exactly three atoms
A lie is: the actor, KNOWING a fact, asserts the opposite to the victim. The benchmark must let a
blind reader recover *who misled whom about what*. That needs exactly three load-bearing facts:

- **a1 — the truth (true_state).** The OBSERVABLE state of the world that makes the actor's claim
  false. NOT the conclusion ("lapsed / void / breached / missed") — that names the answer and lives
  in `answer_key`. Give the observable facts the conclusion follows from, carrying their real
  specifics (dates, figures, references) from the anchor.
- **a2 — the actor knows the truth (knew).** An OBSERVABLE fact putting a1 in the actor's own
  hands: they authored / signed / received / hold / are custodian of the record that carries a1.
  Never "X knew" — a fact a reader can see that implies it.
- **a3 — the false statement (false_statement).** The actor's POSITIVE assertion of the opposite to
  the victim, with NO honest reading — a single quotable line: stated as routine, reassuring, or
  answering a direct question with the wrong answer.

That is all three. The victim's belief/reaction is NOT an atom — it is a RULE (see `reliance_rule`).
Motive is not an atom either: a well-grounded workplace secret is material by construction (someone
acts on a1), so a knowing false statement is deliberate by construction.

## a1 — write OBSERVATIONS, not JUDGMENTS (this decides how many clues the secret can carry)
An atom is ONE thing a reader could SEE in ONE place — one line of one record, one dated instrument.
It is never a conclusion ABOUT what was seen.

A JUDGMENT — over a limit / expired / missing / already past / doesn't match — is NEVER one fact:
no one observes a judgment; it is COMPUTED from two observations. When a1 is a judgment, SPLIT it
into its operands, each its own sub-atom, each **innocuous on its own** (a reader seeing only one has
no reason to suspect anything; only the two together create the contradiction):
  - the REFERENCE — the rule / limit / deadline / term / required value, and
  - the ACTUAL — what a record actually shows, or an absence on file.
  e.g. "the vendor was paid over its contracted cap" → TWO operands:
     a1.1 [record] the master agreement caps this vendor's annual spend at $500k   (just a term)
     a1.2 [record] approved invoices for the vendor this year total $640k           (just a number)

Every operand must be HIDEABLE — a specific fact that can be kept out of a clue and surfaced only in
its own. NEVER make an operand the ambient *current date* / "today", a message's own send-date, or
anything that appears on every email header — that cannot be hidden, so it does not split the secret;
it just leaks the other operand. For an EXPIRY / lapse, the two operands are NOT (end-date)+(today).
They are:
     a1.1 [record] the dated instrument and the term it grants  (e.g. "opinion letter dated 1998-10-01, one-year term")
     a1.2 [record] NO renewal / extension / successor / updated filing on file after it
  The reader infers "lapsed" by combining the term with the *absence* of a renewal — both hideable,
  neither the bare calendar date.

If a1 is a SINGLE record that states the fact outright (a letter that says the guaranty is revoked),
it has ONE operand — there is nothing to compare; the secret is simply shorter (it caps at n=2). That
single operand naturally shows the bad fact when read alone; that is FINE, because the *concealment*
still needs a3 (the false line), which lives in a different clue.

**The number of independent operands of a1 sets how far the secret can be split** (see `n_ceiling`).
Each operand must be innocuous alone and carry its own specifics.

## a2 — is the actor's knowledge OBVIOUS from their role?
Decide and flag it, because it changes whether a2 can stand as its own clue:
- `obvious_from_casting: true` — the actor is, BY ROLE, the custodian of a1 (e.g. "the coordinator
  who holds the file"). A reader infers "they knew" from the casting; a2 cannot be its own necessary
  clue (it rides inside another). Set `core: false`.
- `obvious_from_casting: false` — the actor's knowledge is NOT obvious (they are not the natural
  custodian; they had to receive/discover a1 — e.g. a trader who was forwarded a legal ruling).
  Then a2 carries real information and CAN be its own clue. Set `core: true`.

## a3 — a positive false line, no honest reading
a3 must be a sentence the actor could actually write asserting ¬F. It must be FALSE given a1 with no
charitable reading ("documentation is in order, approved to trade"), not a hedge or an opinion. It
must NOT also state the truth. Carrier is `body`.

## The carrier of each fact (how it will later be embodied)
Tag each operand and a2 with the ONE artifact a reader recovers it from — prefer the structure that
EMBODIES the fact over a line that states it:
  date · sender · recipients · subject · signoff · forward · record · body.

## Rules that are NOT atoms
- `reliance_rule` — the victim's minimal action premised on ¬F (forwards "proceed", books the trade,
  signs), described plainly (NOT "relying on your false assurance"); the victim never challenges, and
  no rebuttal or surfacing of the truth appears in the threads. This keeps the secret unexposed; it
  is grounding, not a clue of its own.
- materiality is guaranteed by the anchor-grounded workplace matter — do not invent a separate fact
  for it.

## Compute n_ceiling
`n_ceiling = (number of a1 operands) + 1` (the +1 is a3), **plus 1** if `a2.obvious_from_casting`
is false (a2 can then be its own clue). This is the most clues this secret can honestly carry.

## Output — ONE JSON object, nothing else
{
  "topic_id": "<<TID>>",
  "secret_type": "lying",
  "actor": "Person X — the concealer, one phrase",
  "victim": "Person Y — the misled party, one phrase",
  "casting_note": "who plays the concealer, who the misled, and why each fits",
  "counterparty": "the real counterparty / matter name from the anchor (or 'the counterparty')",
  "matter": "the deal or file this concealment is about, one phrase",
  "era": "YYYY-MM the events sit in",
  "answer_key": {
    "true_fact": "F — what is actually the case; MAY name the conclusion (lapsed/void/breached/…)",
    "false_belief": "the opposite of F — what the victim is led to believe"
  },
  "a1": {
    "role": "true_state",
    "fact": "the true state F as observable facts with specifics — NOT the conclusion word",
    "is_judgment": true,
    "operands": [
      {"id": "a1.1", "carrier": "record", "fact": "the REFERENCE, innocuous alone, with its specifics"},
      {"id": "a1.2", "carrier": "record", "fact": "the ACTUAL / absence, innocuous alone, with its specifics"}
    ]
  },
  "a2": {
    "role": "knew",
    "carrier": "sender",
    "fact": "the observable fact putting a1 in the actor's own hands (authored/signed/received/holds)",
    "obvious_from_casting": true,
    "core": false
  },
  "a3": {
    "role": "false_statement",
    "carrier": "body",
    "fact": "the actor's positive, quotable assertion of ¬F to the victim — no honest reading"
  },
  "reliance_rule": "the victim's plain action on ¬F (forwards proceed / books / signs); never challenges; no rebuttal in the threads",
  "n_ceiling": 3
}
