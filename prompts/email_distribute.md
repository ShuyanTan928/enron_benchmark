# Distribute — write the clue emails from the plot

You have the full PLOT (your source of truth for every fact, figure, date and specific) and a list
of must-have ATOMS (the facts each clue must establish). Write the benchmark's clue emails.

People are anonymous labels (Person A…J). Never name a real company; the firm is "[firm]".
(Counterparties named in the plot are fine.)

## PLOT — source of truth (write FROM it; do not retell it)
concealer (actor): <<ACTOR>>
misled (victim):   <<VICTIM>>
<<PLOT>>

## THE TEAM — use only these people
<<TEAM>>

## VOICE — write each person in their OWN hand (mandatory, not decoration)
For each person: a style profile, then TWO emails they actually wrote. When that person is a sender,
match their greeting habit, sentence length, punctuation, diction and sign-off to their examples — a
colleague who knows their mail should recognize the hand (Person C is terse and barely greets; Person
H is loose and collegial; etc.). Copy the VOICE ONLY — never reuse any name, company, number, matter
or topic from the examples; those are someone else's content.
<<VOICES>>

## MUST-HAVE ATOMS — every one must end up established in some email
<<ATOMS>>

## REALIZE EACH ATOM THROUGH ITS CARRIER (each atom shows "via <carrier>")
The carrier names the artifact that must carry the fact. Build that artifact so a careful reader
recovers the fact FROM it — and do NOT also spell the concealment-relevant punchline in prose (that
collapses it back to a plain statement and gives the game away):
- via date       — set the message Date, or write a dated instrument/record, so the fact follows from
                   the timing. Mention the instrument neutrally; never append "which is now expired".
- via sender / recipients — let the From / To / Cc carry it: who acted, who was told, who was left off.
- via subject    — put the reference / code / short claim in the Subject line.
- via signoff / forward — carry it in a sign-off / title, or a forwarded-message header (provenance).
- via record     — paste the artifact (a system/log line, a confirmation / invoice / letter reference
                   with its own date) into a body and let its data speak for itself.
- via body       — state it plainly. This is for the speech acts only (the false_assurance, and any
                   reliance in the victim's own words).
What must be PRESENT and unmistakable in a clue is the OBSERVABLE fact (the dated record, the From/To,
the line); what stays INFERRED is the conclusion it implies — never state that. Subtle is the goal,
unreadable is the failure.

## WRITE EXACTLY <<N>> clues. A clue is ONE email thread: a single email, or a reply chain of <= 2
emails on the SAME subject. Never bundle two separate emails into one clue (a new subject, or a
message to a different recipient that is not a reply within that same thread, is a SEPARATE email —
it cannot live in the same clue).
- Assign the atoms across the clues. A [true_state] atom and a [false_assurance] atom NEVER share a
  clue (so no single clue reveals the contradiction).
- If the victim acts on the false assurance ([reliance]): make that clue a 2-message thread on ONE
  subject — message 1 = the actor's assurance to the victim; message 2 = the victim's reply BACK TO
  THE ACTOR (To: the actor, same subject line), DESCRIBING the reliance in their own words. If the
  action is toward a third party (clearing a desk, signing off, relaying onward), the victim still
  DESCRIBES it in this reply to the actor ("clearing the desk on that basis — no unwind required") —
  do NOT address message 2 to that third party, and do NOT thread it onto another conversation.
  Assurance first.
- Every message is exactly ONE email from ONE sender, and every turn is a SEPARATE entry in the
  messages array. NEVER cram a second person's turn into a body — no "---" separator with another
  reply after it, no "[Note appended by …]" / "[X reply, same thread]" stage directions. (Quoting a
  prior email as a forward, under its own "Forwarded message" header, is the one exception.)
- read ALONE, no clue lets a blind reader establish the concealment; read TOGETHER, a careful blind
  reader can reconstruct WHO misled WHOM about WHAT.
- For each clue, write the emails the PEOPLE would actually send, pulling the specifics (figures,
  dates, phrasing) from the plot. Each atom's OBSERVABLE fact must actually be PRESENT in its clue —
  a reader can point to it (the dated line, the header); don't bury it. (Only the conclusion it
  implies stays unstated.)

## WRITE LIKE REAL <<ERA>> CORPORATE EMAIL, not a report or a story:
- write what a real sender would actually put in an email — NOT omniscient narration. Assume shared
  context; be terse; use the shorthand, fragments and rhythm a busy person uses.
- the plot is background truth, not a script: no bulleted chronologies — let facts surface in
  passing, the way they would in real mail.
- light period texture is welcome (a brief sign-off, an abbreviation, a "Re:" reply, a forwarded
  line). If you write a phone/extension use concrete digits — never placeholders like xxx or [name].
- BE A LITTLE SLOPPY, like real fired-off mail — lowercase sentence starts, fragments and run-ons, a
  dropped word or stray typo, "&"/"w/"/"pls", inconsistent spacing. Real 2000 email is not clean even
  prose; perfectly polished paragraphs read machine-made. Keep the load-bearing facts (dates, names,
  the assurance) legible, but don't tidy the rest.
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
