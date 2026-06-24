# Distribute — write the clue emails from the plot

You have the full PLOT (your source of truth for every fact, figure, date and specific) and a list
of must-have ATOMS (the facts each clue must establish). Write the benchmark's clue emails.

People are anonymous labels (Person A…J). Never name a real company; the firm is "[firm]".
(Counterparties named in the plot are fine.)

## PLOT — source of truth (write FROM it; do not retell it)
concealer (actor): <<ACTOR>>
misled (victim):   <<VICTIM>>
<<PLOT>>

## THE TEAM — use only these people; match each sender's tone to their one-line role
<<TEAM>>

## MUST-HAVE ATOMS — every one must end up established in some email
<<ATOMS>>

## WRITE EXACTLY <<N>> clues. A clue is ONE email thread: a single email, or a reply chain of <= 2
emails on the SAME subject. Never bundle two separate emails into one clue (a new subject, or a
message to a different recipient that is not a reply within that same thread, is a SEPARATE email —
it cannot live in the same clue).
- Assign the atoms across the clues. A [true_state] atom and a [false_assurance] atom NEVER share a
  clue (so no single clue reveals the contradiction).
- If the victim acts on the false assurance ([reliance]): make that clue a 2-message thread —
  message 1 = the actor's assurance to the victim; message 2 = the victim's OWN reply, and DESCRIBE
  the reliance there in the victim's words. If the action is toward a third party (clearing a desk,
  signing off, relaying onward), the victim DESCRIBES it in this reply ("clearing the desk on that
  basis — no unwind required") — do NOT write a separate email to that third party. Assurance first.
- Every message is exactly ONE email from ONE sender, and every turn is a SEPARATE entry in the
  messages array. NEVER cram a second person's turn into a body — no "---" separator with another
  reply after it, no "[Note appended by …]" / "[X reply, same thread]" stage directions. (Quoting a
  prior email as a forward, under its own "Forwarded message" header, is the one exception.)
- read ALONE, no clue lets a blind reader establish the concealment; read TOGETHER, a careful blind
  reader can reconstruct WHO misled WHOM about WHAT.
- For each clue, write the emails the PEOPLE would actually send, pulling the specifics (figures,
  dates, phrasing) from the plot. Each atom assigned to a clue must be UNMISTAKABLY established
  there — a reader could point to the line; do not imply it so lightly it could be missed.

## WRITE LIKE REAL <<ERA>> CORPORATE EMAIL, not a report or a story:
- write what a real sender would actually put in an email — NOT omniscient narration. Assume shared
  context; be terse; use the shorthand, fragments and rhythm a busy person uses.
- the plot is background truth, not a script: do not retell it, do not narrate anyone from the
  outside. No bulleted chronologies. Let facts surface in passing, the way they would in real mail.
- light period texture is welcome (a brief sign-off, an abbreviation, a "Re:" reply, a forwarded
  line). If you write a phone/extension use concrete digits — never placeholders like xxx or [name].
- The ONLY placeholder allowed is "[firm]" (the firm itself). Write the counterparty as a natural
  phrase — "the counterparty", or its real name from the plot — never bracket it. No other "[...]"
  tokens at all, and no "[remaining names …]" / list-abbreviation stage directions: write the actual
  content or leave it out.
- Name every cast person by their FULL label — Person A … Person J — everywhere: in From/To, in
  greetings ("Person H," — not "H," or "Hi H"), in sign-offs ("Person C" — not "C"), and inline
  ("Person G and Person I" — not "G and I"). NEVER use a bare single letter for a person.
- never label the concealment: no hide / conceal / cover-up / breach used as an accusation.
<<FEEDBACK>>
Dates fall in the weeks around <<ERA>>, ordered so chains read right. Return ONE JSON object, nothing else:
{"clues":[{"i":1,"carries":["A1","A2"],"messages":[{"from":"Person ?","to":["Person ?"],"cc":[],"date":"YYYY-MM-DD","subject":"...","body":"..."}]}]}
