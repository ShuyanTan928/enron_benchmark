# Step 3 — diagnose the clue set

You see the intended concealment (the answer key) and what an independent blind reader recovered
from the clues. (1) List every failure mode below that applies — none, one, or several — with where
each occurs. (2) Then give one overall revision: why the clue set fails and how to revise the clues
to fix it. Judge by substance, not exact wording.

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

## FAILURE MODES
The atom list is fixed; every fix changes only the emails. A MISSING_* mode means that atom exists
but isn't written into any email — surface it. Never invent or drop an atom.
- SOLO_LEAK            — one clue alone reveals the concealment.
- SUBSET_LEAK          — a proper subset (including all-but-one) reveals it; i.e. some clue isn't load-bearing.
- WRONG_VICTIM         — recovered, but the misled party reads as someone other than <<VICTIM_LABEL>>.
- WRONG_ACTOR          — recovered, but the concealer reads as someone other than the intended actor.
- MISSING_true_state   — the real state isn't fully established, so the false claim can't be shown false.
- MISSING_knew         — nothing shows the concealer knew the truth.
- MISSING_gain         — no motive for concealing is visible.
- WEAK_FALSE_ASSURANCE — the false claim is hedged or has an honest reading.

## Output — return ONE JSON object, nothing else:
{
  "recovered": true | false,
  "modes": [{"mode": "WRONG_VICTIM", "where": "clue 2 / Person B"}],
  "revision": "why the clue set fails and how to revise the clues to fix it"
}
