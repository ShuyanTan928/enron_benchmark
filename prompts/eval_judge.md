# Did the solver recover the intended concealment?

## INTENDED concealment (answer key)
concealer:    <<ACTOR>>
misled:       <<VICTIM>>
true fact:    <<TRUE>>
false belief: <<FALSE>>

## SOLVER'S ANSWER
detection:      <<DET>>
identification: <<IDENT>>

Judge by substance, not wording. Did the solver identify the SAME concealment — the same person
concealing, the same person misled, and the same misrepresented fact? People named slightly
differently are fine if they clearly point to the same person; getting the direction of the lie right
(what is actually true vs what the victim is led to believe) matters.

Return ONE JSON object, nothing else:
{"match": true | false, "reason": "one line"}
