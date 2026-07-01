# Build the ATOMS of one concealment — type: LYING

A deception-detection benchmark hides one concealed fact inside ordinary work emails and tests
whether a model can recover it. Take the SECRET, ground it in the real ANCHOR email, and produce the
three ATOMS — the clean, load-bearing facts the clue emails will later be written FROM. You are NOT
writing emails, choosing how each fact is shown, or splitting/merging anything here — a later step
decides, from the clue count n, how these atoms become observable scenes. Keep each atom MINIMAL and
self-contained: just the fact, with its real specifics from the anchor.

People are anonymous labels (Person A…J). Never name a real company; the firm is "[firm]".
Counterparties named in the anchor are real and stay.

## SECRET — the binary fact to plant
<<TOPIC>>

## ANCHOR — the real email this is grounded in (its matter, dates, counterparty, figures are real)
<<ANCHOR>>

## TEAM — the people you may cast
<<RELATIONSHIPS>>

## The model of a LYING concealment — exactly three atoms
A lie is: the actor, KNOWING a fact, asserts the opposite to the victim. A blind reader must be able
to recover *who misled whom about what*. That needs exactly three clean facts:

- **a1 — the truth (true_state).** The single true fact F that makes the actor's claim false. Write
  JUST that fact with its real specifics (the directive / figure / dated record), NOTHING else. NOT
  the conclusion word ("lapsed / void / breached / over-limit" — that names the answer, it lives in
  `answer_key`). NOT padded with the deal that was done or the victim's action (those are
  `reliance_rule`, not part of a1).
- **a2 — the actor knows the truth (knew).** State the knowing relation plainly: "Person X knows
  <F>." Just that the actor holds F as known. Do NOT decide HOW that knowledge will be made
  observable (received / signed / custodian) — that is chosen later when the clue is written.
- **a3 — the false statement (false_statement).** The actor's POSITIVE assertion of the opposite of
  F, to the victim: "Person X tells Person Y <¬F>." A single quotable claim, FALSE given a1 with no
  honest reading, stated as routine / reassuring / answering a direct question with the wrong answer.
  It must NOT also state the truth.

That is all three. Keep a1 and a3 cleanly OPPOSITE and separable (the truth and the false line can
sit in different emails). The victim's belief/reaction is NOT an atom — it is a RULE (`reliance_rule`
below). Motive is not an atom either: an anchor-grounded workplace secret is material by construction
(someone acts on a1), so a knowing false statement is deliberate by construction.

## Keep the atoms clean — do NOT do the next step's job
- Do NOT tag a carrier or pick how a fact is shown (email date, who's on the To line, a pasted
  record). The later step turns each atom into an observable scene.
- Do NOT merge a1 with a2, or split a1 — the clue count n drives that downstream.
- a1 carries only F. a2 carries only "actor knows F". a3 carries only the false line.

## Rules that are NOT atoms
- `reliance_rule` — the victim's minimal action premised on ¬F (forwards "proceed", books the trade,
  signs), described plainly (NOT "relying on your false assurance"); the victim never challenges and
  the truth never surfaces in the threads. This keeps the secret unexposed; it is grounding.
- materiality is guaranteed by the anchor-grounded workplace matter — do not invent a fact for it.

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
    "fact": "the single true fact F with its real specifics — NOT the conclusion word, NOT the deal/victim action"
  },
  "a2": {
    "role": "knew",
    "fact": "Person X knows <F> — the knowing relation, stated plainly; no observable form chosen yet"
  },
  "a3": {
    "role": "false_statement",
    "fact": "Person X tells Person Y <¬F> — one quotable false line, false given a1, no honest reading, not stating the truth"
  },
  "reliance_rule": "the victim's plain action on ¬F (forwards proceed / books / signs); never challenges; no rebuttal in the threads"
}
