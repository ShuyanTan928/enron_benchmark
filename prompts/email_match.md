# Did the blind read recover the intended concealment?

## INTENDED concealment
concealer:    <<ACTOR>>
misled:       <<VICTIM>>
true fact:    <<TRUE>>
false belief: <<FALSE>>

## BLIND READ produced
<<PROBE>>

Judge by substance, not wording. Does the blind read identify the SAME concealment — the same
person concealing, the same person misled, and the same misrepresented fact? Roles named slightly
differently are fine if they clearly point to the same people and the same fact.

Return ONE JSON object — nothing else:
{
  "match": true | false,
  "reason": "one line"
}
