# Place one worked-out secret on the atom skeleton — <<ACT_NAME>>

The secret below is already decided — its true fact, the false belief, and the concealing act.
Put those onto the three fixed atoms, cast the people, carry the rest across.

## The three atoms
- a1 — the objective truth (a checkable state of affairs).
- a2 — the actor knew the truth.
- a3 — the actor's concealing act: <<A3_ACT>>

## The secret to place
<<TOPIC>>

## Rules
(none yet)

## The people and how they relate
<<RELATIONSHIPS>>
Map the topic's roles onto them: the ACTOR holds the true side and conceals; the VICTIM acts on the false side.

## Anchor — the real email this work secret sits on
<<ANCHOR>>

## Example
<<EXAMPLE>>

## Output — ONE JSON object, nothing else
{
  "topic_id": "<<TID>>",
  "secret_type": "<<TYPE>>",
  "actor": "Person X — the concealer",
  "victim": "Person Y — the misled party",
  "counterparty": "outside party / matter, or 'n/a'",
  "matter": "the matter this is about — one phrase",
  "era": "<<ERA_NOTE>>",
  "answer_key": { "true_fact": "<carry the topic's true_fact>", "false_belief": "<carry the topic's false_belief>" },
  "a1": { "role": "true_state", "fact": "the truth as a standing status — no event, no document" },
  "a2": { "role": "knew", "fact": "Person X knows <a1>" },
  "a3": { "role": "<<A3_ROLE>>", "fact": "the concealing act toward the victim (per a3 above)" }
}
