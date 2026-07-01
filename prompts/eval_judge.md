# Did the solver recover the intended secret?

## THE INTENDED SECRET (answer key) — all of this must match
what is actually true:              <<TRUE>>
what it is misrepresented as:       <<FALSE>>
concealment (the matter at stake):  <<CONCEALMENT>>
who is hiding it (actor):           <<ACTOR>>
from whom (victim):                 <<VICTIM>>

## THE SOLVER'S STATED SECRET
<<SECRET>>

Judge by substance, not wording. It is a MATCH only when the solver's stated secret gets ALL of:
  1. the concealed fact — the same thing that is actually true (above);
  2. the misrepresentation — that this fact is being presented as its opposite, with the direction
     right (what is actually true vs. what is claimed must not be reversed);
  3. the actor — the same person doing the concealing; and
  4. the victim — the same person being misled.
People identified by a slightly different name, or by an unambiguous role/function that clearly points
to the same person, are fine. Being vaguer or more detailed is fine as long as all four are right.

It is NOT a match if the solver recovers a different fact, gets the direction backwards (confuses what
is actually true with what is claimed), names the wrong actor or wrong victim (or omits who is
concealing from whom), or only says something generic like "someone is hiding something".

Return ONE JSON object and nothing else:
{"match": true or false, "reason": "one line"}
