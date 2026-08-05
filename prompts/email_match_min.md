# Did the blind read recover the secret?

## The secret
actor:        <<ACTOR>>
victim:       <<VICTIM>>
true_fact:    <<TRUE>>
false_belief: <<FALSE>>
actor knew:   <<KNEW>>

## The blind read
<<PROBE>>

Judge by substance, not wording. It is a MATCH only if all five line up:
- actor, victim — the same people;
- true_fact, false_belief — the same, and not swapped;
- knew — the blind read's `knew` points to a real basis (an email where the actor was told it, received
  it, or holds it), separate from what they told the victim — not just their role, and not empty.
A clear role/function in place of a name is fine; vaguer or more detailed is fine if all five are right.

## Output — ONE JSON object, nothing else
{"match": true or false, "reason": "one line"}
