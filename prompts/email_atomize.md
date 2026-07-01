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
- true_state      — the OBSERVABLE fact that makes the false claim false (a dated record, an absence
                    on file) — NOT the conclusion it implies ("void / lapsed"); that names the true
                    side of the binary and lives in the answer key. Leave the numbers to the plot.
- knew            — an OBSERVABLE fact putting the truth in the concealer's own hands: they ran it,
                    executed / signed it, hold the file, or acted before the required step. Never a
                    claim about their mind ("X knew…") — a fact a reader can see that implies it.
- false_assurance — the concealer asserting the opposite to the victim, with no honest reading.
- reliance        — a consequential action the victim takes because they believe the false version.
- gain            — (optional) the cost the truth would trigger, as ONE neutral clause. Skip it when
                    the plot already makes the motive plain.

## CARRIER — also tag each atom with the ONE artifact a reader recovers it FROM. Real concealment is
often given away by a timestamp or a recipient list, not a sentence. Prefer the structure that
naturally EMBODIES the fact over a line that states it. Pick exactly one:
- date       — a message's Date, or a dated instrument/record (a letter dated X, a renewal due Y). For
               timing / lapse / sequence: the reader infers it from WHEN, not from a line calling it so.
- sender     — who a message is From: authorship showing who acted / holds it / asserted it.
- recipients — the To/Cc list, or a pointed absence from it: who was told, who was kept out of the loop.
- subject    — a subject line, or a reference / matter / file code in it.
- signoff    — a sign-off, title or letterhead naming a role or entity.
- forward    — a quoted/forwarded prior-message header: provenance ("from X, dated Y").
- record     — a quoted artifact pasted into a body (a system/log line, a confirmation or invoice
               number, an opinion-letter reference with its own date); the fact rides the artifact's
               data, not the narration around it.
- body       — said in plain text. Use ONLY for a speech act that can only be spoken — chiefly the
               false_assurance (and a reliance stated in the victim's own words).

Bias by role (choose the most natural for THIS scene; never force a carrier that doesn't fit):
true_state -> date / record ; knew -> sender / date / forward ; false_assurance -> body ;
reliance -> recipients / forward / body ; gain -> body, or leave it to the plot.

## How to write an atom — write OBSERVATIONS, not JUDGMENTS
An atom is ONE thing a reader could SEE in ONE place — one line of one document, one record entry,
one email header, one sentence someone wrote. It is never a conclusion ABOUT what was seen.

- A JUDGMENT — something is wrong / over a limit / missing / late / expired / lapsed / doesn't match
  — is NEVER one atom, because no one observes a judgment: it is COMPUTED by putting two observations
  together. Name the two observations instead — the REFERENCE (the rule, limit, deadline, standard,
  required value) and the ACTUAL (what a record actually shows) — each its own atom. The test: each
  operand must be INNOCUOUS ON ITS OWN — a reader seeing only one has no reason to suspect anything;
  only the two together create the contradiction. (That gap is exactly what lets the secret be split
  across emails — a fact that looks wrong by itself isn't a distributed clue, it's a one-email leak.)
    e.g. "the vendor was paid over its contracted cap" is TWO atoms:
       [the master agreement caps this vendor's annual spend at $500k]  (reference — just a term)
     + [approved invoices for the vendor this year total $640k]         (actual — just a number)
  But if the truth is a SINGLE record that states the fact outright (a letter that says the guaranty
  is revoked), that is ONE atom — there is nothing to compare; the secret is simply shorter.
- The false claim is ONE atom: a single speech act — "Person X told Person Y that [the false
  version]." Indivisible even though it carries who/whom/what at once.
- Each atom asserts exactly ONE fact: split any "X and that Y" or comma-spliced double claim. Where a
  split leaves a half that just paraphrases another atom, keep the single clearest phrasing.
- State only what is observably the case — no "because / so that", no gloss on meaning or intent.

## CORE vs SUPPORT — which atoms carry the AND-logic
A blind reader reconstructs the concealment only from atoms that are INFORMATIONALLY INDEPENDENT —
none derivable from the others plus the plain casting. Mark each:
- core: true  — without it the contradiction cannot be assembled. These are the true_state OPERANDS
                and the false claim. They set how many clues the secret can carry (one core per clue).
- core: false — a reader would already INFER it from the core atoms + who these people are: the actor
                KNEW (they own / signed / authored the record); the victim ACTED (a material false
                claim gets acted on); the motive. Support RIDES ALONG in a core clue, never its own.
  Exception: if a knew/motive fact is genuinely NOT inferable (the actor had to actively discover
  something outside their normal view), mark it core.

## Output — ONE JSON object, nothing else:
{"topic_id":"<<TID>>","atoms":[{"id":"A1","role":"true_state","carrier":"record","core":true,"fact":"..."}]}
