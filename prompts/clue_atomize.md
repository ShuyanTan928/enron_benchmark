# Step 3A — atomize one concealment into role-tagged facts

You are given a SECRET (a deliberate concealment) and its SCENE (the Step-2 plot it plays out in).
Break the concealment into the MINIMAL facts a reader would need to reconstruct it, each tagged
with exactly ONE role. Do NOT write any emails here — produce only the atoms.

People are anonymous labels (Person A…). Never name a real company.

## THE SECRET — what is concealed
<<SECRET>>

## THE SCENE — your source of truth for every specific (same deal, figures, people, dates)
concealer: <<ACTOR>>
misled:    <<VICTIM>>
PLOT:
<<PLOT>>

## ROLES — tag every atom with exactly one
  • true_state      — a fact about what is actually the case (the real status / figure). If it is
                      rich, split it into several atoms (e.g. the real figure; AND that a lower
                      figure quoted elsewhere is the stale one). Make the true state COMPLETE:
                      include whatever a reader needs to see that the false assurance is false.
  • knew            — a fact putting the true state in the concealer's own hands: they ran it,
                      were told it, or hold the file.
  • gain            — the concrete cost the truth would trigger, which the lie avoids. Write it as
                      a NEUTRAL FACT — never as a stated wish to hide.
  • false_assurance — the concealer asserting the opposite to the misled party, phrased so it is
                      UNAMBIGUOUSLY the false version: no hedge, no alternative metric, no reading
                      under which the statement could be honest.
  • reliance        — (OPTIONAL) a concrete, consequential action the MISLED party takes BECAUSE
                      they believe the false version — something that only makes sense if the false
                      assurance were true (they direct / authorize / commit / proceed on it).
                      Include this when it helps make clear WHO is being misled: the misled party
                      is whoever is seen acting on the false belief.

There must be at least one atom each of true_state, knew, gain, false_assurance. Split true_state
into as many atoms as the secret needs; keep every atom a single fact.

## Output — return ONE JSON object, nothing else:
{
  "topic_id": "<<TID>>",
  "atoms": [
    {"id": "A1", "role": "true_state", "fact": "..."},
    {"id": "A2", "role": "knew", "fact": "..."}
  ]
}
