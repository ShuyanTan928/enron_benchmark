# Design each clue's observable scene

You're given the atoms and a fixed plan of which atom each clue carries. For each clue, write one
observable scene (`plot`, 1–2 sentences) to help a later step turn it into a real work email.

Firm people are Person A…J; outside parties keep real names; our company is "[firm]".
The events sit in <<ERA>> — date every record and message within 2000–2001.

## The matter
actor (conceals): <<ACTOR>>   victim (misled): <<VICTIM>>

## The team — use only these
<<TEAM>>

## The plan — each clue carries only its listed atom(s)
<<ASSIGNMENT>>
One thread per clue on its own subject, never a reply to another clue; two messages, or three for a3.

<<SEPARATION>>

## Rules
1. each clue shows only its own atom(s); the leaks are surface tells — e.g. the actor on the truth clue,
   the truth as the actor's own copy, or a subject that spells the outcome ("…terminated…"). name the matter, not the result.
2. close the timing gap: if the truth could later resolve, date it at or after the act, or make it standing.
3. a clue is something a reader can observe (a date, a figure, a subject line, who wrote to whom), never a mental state.
4. name any attached or forwarded file the way real Enron files were named — plain descriptive words, often a date, a .doc/.xls/.pdf, like the example — not an invented letter-code.
5. name the subject a fact is about: the record carrying the truth names them, and any clue speaking of them names the same person — hide only the other clues' atoms, never the subject's identity.

## Example
<<EXAMPLE_PLOT>>

<<FEEDBACK>>
Return ONE JSON object, nothing else:
{"clues":[{"i":1,"carries":["a1"],"plot":"the observable scene","isolated":"the other clues' atoms this must not reveal, and why its sender/recipients/reference/whose-copy/dates show none of them"}]}
