# Step 3 — diagnose the clue set

You see the intended concealment (the answer key) and what an independent blind reader recovered
from the clues. (1) List every failure mode below that applies — none, one, or several — with where
each occurs. (2) Then give one overall revision: why the clue set fails and how to revise the clues
to fix it. Judge by substance, not exact wording.

## The architecture you are diagnosing — hold it firmly
The concealment is split across the clues so that NO proper subset reveals it — only ALL of them
together do. Three load-bearing pieces: the TRUTH (a1), that the actor KNEW it (a2), and the actor's
FALSE claim to the victim (a3). Each clue carries ONLY its own piece. A subset LEAKS exactly when a
clue has taken on ANOTHER clue's piece — the truth clue also showing the actor knew (the actor
authored / received / holds that record), or a clue restating WHAT another clue's record says. So
every fix must remove the overlap WITHOUT creating a new one: to show the actor KNEW, have them hold
the SAME named record by its reference / handle, NEVER by repeating its content into their clue.

## INTENDED concealment
concealer (actor): <<ACTOR>>
misled (victim):   <<VICTIM>>
true fact:         <<TRUE>>
false belief:      <<FALSE>>

## CLUE SET — atoms (with roles) + emails
<<CLUES>>

## What the blind reader recovered from all clues together
<<JOINT>>

## Leakage findings — single clues / proper subsets
<<LEAKAGE>>

## Structural findings — is each clue ONE clean email thread?
<<STRUCTURE>>

## Revisions already tried on this clue set — do NOT repeat or reverse them; build on them
<<HISTORY>>

## FAILURE MODES
The atom list is fixed; every fix redesigns the observable SCENES (which named record carries each
fact, who receives / holds it, the dates and references) — never the atoms. A MISSING_* mode means
that atom exists but no scene makes it observable — surface it. Never invent or drop an atom.
If the blind reader recovered NOTHING, say WHY the full set reads as innocent — name the reconcilable
reading (e.g. a date gap that lets "not received yet" and "signed and on its way" both be true; the
actor's held record never tied to the truth document) — and how to remove it (same dates, the SAME
named record in the knowledge scene and the truth scene, a claim that can't be read as in-transit).
- SUBSET_LEAK          — a proper subset (down to a SINGLE clue alone, the extreme case) reveals the
  concealment on its own, so a clue in it carries a piece that belongs to ANOTHER clue. From the
  evidence the reader leaned on (in Leakage findings), name WHICH clue carries WHICH foreign piece,
  and how to move it out — e.g. the truth clue also proving the actor knew (because the actor authored
  / received / holds that very record — INCLUDING being merely one of several recipients / cc's on the
  truth email; the actor must not be on the truth clue at all), or a clue restating what another clue's
  record SAYS, etc.
- WRONG_VICTIM         — recovered, but the misled party reads as someone other than <<VICTIM_LABEL>>.
- WRONG_ACTOR          — recovered, but the concealer reads as someone other than the intended actor.
- MISSING_true_state   — the real state isn't fully established, so the false claim can't be shown false.
- MISSING_knew         — NO scene shows the actor knew at all; the knowledge piece is simply absent.
- UNLINKED             — the actor IS shown holding a record, but it is not tied to the truth record, so
  a reader can't conclude they knew THE truth. Fix by naming the SAME record (one shared reference /
  handle) in both the knowledge scene and the truth scene — never by copying the truth's content over.
- WEAK_FALSE_ASSURANCE — the FALSE CLAIM itself is soft: hedged, or it has an honest reading on its own.
  (If the claim is sharp but the whole set still reconciles innocently, that is ALTERNATIVE_EXPLANATION.)
- ALTERNATIVE_EXPLANATION — read all together, the clues have a REASONABLE innocent explanation OTHER
  than the actor concealing the secret (e.g. a timing gap that reconciles the two facts, an "in
  transit / arriving later" reading, two unrelated matters, etc.). In the revision, NAME that innocent
  explanation explicitly, then say how to remove it (e.g. pin the truth and the claim to the same
  point in time, or a claim that can't be read as "on its way") so the actor's knowing concealment is
  the ONLY reading.
- NOT_ONE_THREAD        — a clue (see Structural findings) isn't one clean thread: a message embeds or
  forwards another turn. Work out WHAT it pulled in — often another clue's content dragged in along
  with a forwarded/quoted message — and how to redo that scene so the clue stands alone with only its
  own piece (e.g. point at a shared record by its name/reference instead of carrying the message in).

## Output — return ONE JSON object, nothing else:
{
  "recovered": true | false,
  "modes": [{"mode": "WRONG_VICTIM", "where": "clue 2 / Person B"}],
  "revision": "2-3 sentences: the failure in plain terms — for a leak, WHICH clue carries WHICH foreign piece (cite the evidence) and the concrete scene change that moves it out without a new overlap; for a non-recovery, what innocent reading survives and how to kill it"
}
