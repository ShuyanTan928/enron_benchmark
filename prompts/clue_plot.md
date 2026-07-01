# Design the observable scene (plot) for each clue

You are given a concealment's three clean ATOMS and a FIXED plan saying which atom(s) each clue must
carry. For EACH clue, design ONE observable scene — its `plot`, one or two plain sentences — that a
later step will write as a real email. You decide WHAT each clue shows, as plain observable fact.

People are anonymous labels (Person A…J). Never name a real company; the firm is "[firm]". The
counterparty named below is real and stays.

## THE MATTER
concealer (actor): <<ACTOR>>
misled (victim):    <<VICTIM>>
counterparty / matter: <<COUNTERPARTY>> — <<MATTER>>

## THE TEAM — use only these people
<<TEAM>>

## THE PLAN — which atom(s) each clue carries
<<ASSIGNMENT>>

## The AND principle — the one thing the whole set must satisfy
A lie has THREE load-bearing pieces, and a reader can conclude "the actor KNOWINGLY misled the
victim" only when ALL THREE are in hand:
  • the TRUTH F (a1);
  • that the ACTOR KNEW F (a2);
  • the ACTOR's FALSE CLAIM of ¬F to the victim (a3).
The whole benchmark rests on keeping these apart: each clue shows ONLY its own piece and gives away
NOTHING about the other two — so that no single clue, and no PARTIAL combination of clues, lets a
reader establish the deliberate lie; only ALL the clues together do.

So as you design each clue, picture exactly what a reader takes from it and keep the OTHER two pieces
invisible inside it — reason it through, don't run a checklist. (A clue assigned more than one piece
— e.g. a1+a2 merged — may carry both: with so few clues there is no partial combination left to
expose the lie. When a1 is split into a1.1/a1.2, make each half innocuous alone; together recover F.)

## A plot never carries another plot's content — point at shared things, don't repeat them
Two clues will often need to touch the SAME thing — the record that holds the truth, and the actor
receiving that record. When they overlap like that, point at it with a DEFINITE REFERENCE — anything
concrete that pins it to one object (a filename, a reference number, a dated title, etc.) — so a
reader sees it is one and the same object; but state that object's CONTENT only in the plot whose
piece the content is. The reference is shared; the content is not.
  e.g. both plots may name `LC-DBK-0047_redline.docx` to show it is one document. Only the TRUTH plot
  says what that file CONTAINS (its provisions are non-standard); the other plot just shows the actor
  received / holds `LC-DBK-0047_redline.docx`, never what it says. The moment that second plot states
  the file's content, it has taken on the truth piece too, and the two leak together.
Without a shared reference the full set also fails the other way: "the attached correspondence" with
no identifier leaves the actor's receipt floating free of the truth record, so a reader can't connect
them and nothing is recoverable. Name the same thing in both; reveal its content in only one.

## Make the truth still hold at the moment of the claim
If the truth is a "not yet / still missing / pending / unsigned / unfiled" kind of state — anything
that could later RESOLVE — a reader can always reconcile it with the false claim by "it changed in
between" (it arrived / got signed / got filed after the truth scene). Close that gap: the truth scene
must show the state STILL holds when, or after, the actor makes the false claim — date the truth at or
after the claim, or render it as a standing record that has not changed — so there is no window for
the state to have flipped. The truth the reader sees must still be true at the instant of the lie.

## Self-check before you finalize — read it as the grader will
Walk every subset of your clues and ask: does it let a reader establish that someone KNOWINGLY
misrepresented a fact?
  • each clue ALONE — must NOT. Alone, each clue is ordinary, unremarkable work mail.
  • each PAIR — must NOT. truth + false-claim leaves it unproven that the claimant knew (so don't put
    the truth record in the actor's own hands — that pair would then prove it); knowledge + false-claim
    never shows the held record CONTRADICTS the claim; truth + knowledge has no claim yet.
  • ALL together — now the knowing misrepresentation is establishable, AND it is the ONLY reasonable
    explanation. If any innocent reading still survives — a timing gap (see "truth still hold at the
    moment of the claim" above), two unrelated matters, an honest mistake, etc. — the contradiction is
    too soft; tighten it so the actor knowingly concealing the secret is the only way to read it.
If any single clue or any pair already gives it away, that clue is carrying more than its own piece.
Find which other piece leaked in, pull it out, and re-describe the scene. Iterate until every proper
subset reads as innocent and only the full set reveals the lie.

## Keep it observable and independent
- OBSERVABLE FACT ONLY — anything a reader can SEE in the mail (a dated record, a figure, a subject
  line, who sent what to whom, etc.). NEVER a mental state or verdict — words like "knew / realized /
  concealed / unauthorized".
- Clues are INDEPENDENT — each is its own email/thread, never a reply to (or sharing a subject with)
  another clue. A clue MAY be a <=2-message chain WITHIN itself — e.g. the false claim + the victim's
  brief reply.
- Each plot fits ONE email round.
<<FEEDBACK>>
Return ONE JSON object, nothing else:
{"clues":[{"i":1,"carries":["a1","a2"],"plot":"the observable scene this clue shows"}]}
