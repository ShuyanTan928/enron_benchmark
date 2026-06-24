# Step 3B — distribute the given atoms into N clue emails

You are given a SECRET, its SCENE, and a fixed list of role-tagged ATOMS. Distribute the atoms
into exactly <<N>> clues and write each clue's email(s) — so that:
  • read ALONE, each clue is ordinary business and reveals the secret to no one;
  • read TOGETHER, all <<N>> let a careful reader reconstruct the concealment;
  • everything stays faithful to the SCENE's specifics — same deal, figures, people, dates.

A clue is one email, or a chain of at most two emails counted as one clue. People are anonymous
labels (Person A…); write over the labels. Never name a real company.

## THE SECRET — what is concealed
<<SECRET>>

## THE SCENE — source of truth for every specific
concealer: <<ACTOR>>
misled:    <<VICTIM>>
PLOT:
<<PLOT>>

## ATOMS — use ALL of them; do not invent new facts, do not drop any
<<ATOMS>>

## TEAM — who may appear (address everyone by their Person label)
<<TEAM>>

## STEP B — ASSIGN every atom to one of the <<N>> clues
  • HARD RULE: never put a true_state atom and a false_assurance atom in the SAME clue — their
    contradiction IS the secret, so that clue would give it away on its own.
  • No single clue, read alone, may let a reader reconstruct the concealment. If a clue's atoms
    together would, spread them across clues.
  • Every atom goes in exactly one clue; every clue holds at least one atom.

## STEP C — WRITE each clue
Write each clue's email(s) carrying ONLY its atoms, as plain business mail. Address everyone by
Person label. Date within a few weeks of <<ERA>>, ordered: the true state before the false
assurance; any reliance after. No clue names the secret or uses words like hide / conceal / cover
/ breach as a label. Keep bodies lean — only what the atoms need. (Voice/tone is polished in a
later pass; here, just get the facts and structure right.)

## Output — return ONE JSON object, nothing else. The "carries" list references the atom ids above:
{
  "topic_id": "<<TID>>",
  "clues": [
    {"i": 1, "carries": ["A1", "A2"],
     "messages": [
       {"from": "Person X", "to": ["Person Y"], "cc": [], "date": "YYYY-MM-DD", "subject": "...", "body": "..."}
     ]}
  ]
}
