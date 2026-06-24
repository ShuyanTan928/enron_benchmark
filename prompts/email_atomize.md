# Atomize — the must-have facts of one concealment

You are given a SECRET (a deliberate concealment) and its PLOT (the full scene it plays out in).
Produce the SMALLEST set of facts a blind reader would need to reconstruct the concealment — only the
load-bearing ones. The PLOT already holds every figure, date and specific, and the clue emails will
be written FROM the plot — so do NOT copy figures or detail into the atoms.

People are anonymous labels (Person A…). Never name a real company; the firm is "[firm]".

## SECRET
<<SECRET>>

## PLOT — the source the emails will be written from
concealer (actor): <<ACTOR>>
misled (victim):   <<VICTIM>>
<<PLOT>>

## ROLES — tag each atom with exactly one; produce only the must-haves:
- true_state      — the real state that makes the false claim false (the true side of the binary).
                    State it qualitatively; leave the numbers to the plot.
- knew            — an OBSERVABLE fact putting the truth in the concealer's own hands: they ran it,
                    executed / signed it, hold the file, or acted before the required step. Never a
                    claim about their mind ("X knew…") — a fact a reader can see that implies it.
- false_assurance — the concealer asserting the opposite to the victim, with no honest reading.
- reliance        — a consequential action the victim takes because they believe the false version.
- gain            — (optional) the cost the truth would trigger, as ONE neutral clause. Skip it when
                    the plot already makes the motive plain.

## How to write an atom
- Each atom is INDIVISIBLE: it asserts exactly ONE fact. If a statement makes two claims — joined by
  "and", "and that", or a comma splicing two claims — it is two atoms, not one. This holds even for a
  single speech act: "C told D that X and that Y" becomes two atoms — "C told D that X" / "C told D
  that Y". Likewise a true state evidenced two ways ("never sought, and no record exists") is two atoms.
- State only what is observably the case. No reasoning, no "because / so that", no gloss on what it
  means or what anyone intended — the blind reader supplies that.
- Lean: keep only the load-bearing must-haves that pin WHO concealed WHAT from WHOM and that it was
  deliberate. No second figures, corroborating repeats, or supporting colour — the plot carries those.
  If splitting leaves a half that merely restates another atom, drop the restatement.

Before returning, re-read every atom: split any that asserts two different facts; and where an atom
joins a claim to a paraphrase of itself ("no hard stop and a caution rather than a block"), keep only
the single clearest phrasing.

## Output — ONE JSON object, nothing else:
{"topic_id":"<<TID>>","atoms":[{"id":"A1","role":"true_state","fact":"..."}]}
