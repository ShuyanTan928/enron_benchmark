# Write the clue emails from their plots — each in its sender's own voice

You are given, for each clue, the observable SCENE it must show (its `plot`) and which atom(s) it
carries. Turn each clue's plot into a real email — one message, or a <=2-message reply chain on one
subject — written in the SENDER'S OWN VOICE. Embody the plot; add no fact, drop no fact, change
nothing about what each clue shows.

People are anonymous labels (Person A…J). Never name a real company; the firm is "[firm]". The
counterparty named below is real and stays.

## THE MATTER
concealer (actor): <<ACTOR>>
misled (victim):    <<VICTIM>>
counterparty / matter: <<COUNTERPARTY>> — <<MATTER>>

## THE TEAM — use only these people
<<TEAM>>

## VOICE — write each sender in their OWN hand (mandatory)
For each person: a style profile, then TWO emails they actually wrote. When a person is a sender,
match their greeting habit, sentence length, punctuation and sign-off to their examples. Copy the
VOICE ONLY — never reuse any name, company, number, matter or topic from the examples.
<<VOICES>>

## THE CLUES TO WRITE — one email (thread) per clue, embodying its plot
<<PLOTS>>

## Embody the plot, don't narrate it
Build the artifact so a careful reader recovers the fact FROM it; do NOT also spell the punchline in
prose. Use whatever carrier fits the plot:
- date — set the message Date, or write a dated instrument/record, so the fact follows from timing.
  Mention the instrument neutrally; never append "which is now expired".
- sender / recipients — let From / To / Cc carry it: who acted, who was told, who was left off.
- subject — put the reference / code / short claim in the Subject line.
- signoff / forward — carry it in a sign-off / title, or a forwarded-message header (provenance).
- record — paste the artifact (a system/log line, a confirmation / invoice / letter reference with
  its own date) into a body and let its data speak for itself. Give a load-bearing document a
  concrete handle — a filename, a tracking/reference number, a dated title, etc. — and when another
  clue refers to THE SAME document (e.g. the actor receiving it), name it by that SAME handle, never a
  vague "the attached" — that shared handle is how the clues link.
- body — state it plainly. Use for the false statement and the victim's plain reliance only.
What must be PRESENT in a clue is the OBSERVABLE fact; what stays INFERRED is the conclusion — never
state that. Subtle is the goal, unreadable is the failure: the plot's fact must actually be there.

## THE FALSE STATEMENT AND RELIANCE (the a3 clue)
The clue carrying a3 is where the actor asserts the false version to the victim. If its plot attaches
the victim's reliance, make it a 2-message thread on ONE subject: message 1 = the actor's assertion
to the victim; message 2 = the victim's SHORT reply BACK TO THE ACTOR (To: the actor, same subject).
- The victim TAKES THE ACTOR AT THEIR WORD: never questions, challenges, double-checks, or asks for
  proof of the clearance; the truth NEVER surfaces in any thread.
- Keep the reply terse and natural, the way a busy person actually fires one off — a quick "ok" plus
  what they'll do next ("ok thx, releasing it to the desk"). Do NOT mechanically REPEAT or restate
  the counterparty, the deal id, the figures, or the actor's own sentence back at them — nobody
  echoes the details they were just told. Write the reliance as a plain action, NEVER as "relying on
  your false assurance".

## EACH CLUE IS ONE CLEAN, INDEPENDENT EMAIL THREAD
- A clue is ONE email, or a reply chain of <= 2 emails on the SAME subject. Never bundle two
  separate emails (a new subject, or a message to a different recipient that is not a reply in that
  same thread) into one clue.
- Clues are INDEPENDENT of each other: each clue is its OWN thread on its OWN subject. NEVER write one
  clue as a reply to another clue's email, and never reuse another clue's subject line — different
  clues must not share a thread. And no clue restates, forwards, or quotes the content another clue
  carries; each says only its own fact.
- Every message is exactly ONE email from ONE sender, a SEPARATE entry in the messages array. NEVER
  cram a second person's turn into a body — no "---" separator with another reply after it, no
  "[Note appended by …]" / "[X reply, same thread]" stage directions. (A forwarded prior message
  under its own "Forwarded message" header is the one exception.)

## WRITE LIKE REAL <<ERA>> CORPORATE EMAIL, not a report or a story
- write what a real sender would actually put in an email — terse, assuming shared context, the
  shorthand and rhythm of a busy person. No bulleted chronologies; let facts surface in passing.
- BE A LITTLE SLOPPY, like real fired-off mail — lowercase sentence starts, fragments and run-ons, a
  dropped word or stray typo, "&"/"w/"/"pls", inconsistent spacing. Keep the load-bearing facts
  (dates, names, the false line) legible; don't tidy the rest. Perfectly polished prose reads
  machine-made.
- light period texture is welcome (a brief sign-off, an abbreviation, a "Re:" reply, a forwarded
  line). If you write a phone/extension use concrete digits — never placeholders like xxx or [name].
- The ONLY placeholder allowed is "[firm]". Write the counterparty as its real name or a natural
  phrase ("the counterparty") — never bracket it. No other "[...]" tokens, no "[remaining names …]"
  list-abbreviation directions: write the actual content or leave it out.
- Name every cast person by their FULL label — Person A … Person J — everywhere: From/To, greetings
  ("Person H," not "H,"), sign-offs ("Person C" not "C"), inline ("Person G and Person I"). NEVER a
  bare single letter for a person.
- never label the concealment: no hide / conceal / cover-up / breach used as an accusation.
<<FEEDBACK>>
Dates fall in the weeks around <<ERA>>, ordered so chains read right. Return ONE JSON object, nothing else:
{"clues":[{"i":1,"carries":["a1","a2"],"plot":"...","messages":[{"from":"Person ?","to":["Person ?"],"cc":[],"date":"YYYY-MM-DD","subject":"...","body":"..."}]}]}
