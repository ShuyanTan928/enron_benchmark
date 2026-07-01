# Turn the atoms into clue emails — plot each clue, then write it

You are given a concealment's three clean ATOMS with their real specifics, and a FIXED plan that says
exactly which atom(s) each clue must carry. For EACH clue you do two things, in order:
  STEP 1 — turn its assigned atom(s) into ONE observable scene (the clue's `plot`);
  STEP 2 — write that scene as a real email (one message, or a <=2-message reply chain).
Each clue embodies its assigned fact(s) and nothing more.

People are anonymous labels (Person A…J). Never name a real company; the firm is "[firm]". The
counterparty named below is real and stays.

## THE MATTER — shared context every clue is consistent with
concealer (actor): <<ACTOR>>
misled (victim):    <<VICTIM>>
counterparty / matter: <<COUNTERPARTY>> — <<MATTER>>
Keep every clue consistent with these: same counterparty, same dates and figures, same people.

## THE TEAM — use only these people
<<TEAM>>

## VOICE — write each sender in their OWN hand (mandatory)
For each person: a style profile, then TWO emails they actually wrote. When a person is a sender,
match their greeting habit, sentence length, punctuation and sign-off to their examples. Copy the
VOICE ONLY — never reuse any name, company, number, matter or topic from the examples.
<<VOICES>>

## THE PLAN — which atom(s) each clue carries
<<ASSIGNMENT>>

## STEP 1 — turn each clue's atom(s) into ONE observable plot
For each clue, design a single observable scene that carries exactly its assigned atom(s) and fits
ONE email round. Write that scene into the clue's `plot` field (one or two plain sentences), then
realize it as the email. Rules:
- **OBSERVABLE FACT ONLY.** A plot is what a reader can SEE in the mail — a dated record, a figure, a
  subject line, who sent what to whom. NEVER a mental state or a verdict: no "knew / realized / was
  aware / concealed / unauthorized". Those are the answer, not the scene.
- **MERGE when a clue carries more than one atom.** Build ONE observation that carries them all at
  once — do not stitch two separate facts. e.g. a clue carrying a1+a2: the record that IS the truth
  (a1), sent straight TO the actor or signed by them (a2 = they hold it) — a single email does both.
- **a2 (the actor knows) becomes OBSERVABLE here.** Realize "knows" as a visible handle: the actor
  authored it, is the To/Cc, received it, or is named custodian on the record. Never write the word
  "knew" / "aware" in the email — let the From/To/record show it.
- **SPLIT when a clue carries `a1.1` or `a1.2`.** These are the two halves of the truth a1: split a1
  into two observations, each INNOCUOUS on its own (neither reveals the truth alone), which read
  together recover a1 — one half in the a1.1 clue, the other in the a1.2 clue.
- **No clue self-sufficient.** A clue read ALONE must not reveal the concealment; only all clues read
  TOGETHER may. Do not let any other atom's fact, or the CONCLUSION it implies, appear in a clue.

## STEP 2 — embody the plot in the mail, don't narrate it
Build the artifact so a careful reader recovers the fact FROM it; do NOT also spell the punchline in
prose. Pick whatever carrier fits the plot:
- date — set the message Date, or write a dated instrument/record, so the fact follows from timing.
  Mention the instrument neutrally; never append "which is now expired".
- sender / recipients — let From / To / Cc carry it: who acted, who was told, who was left off.
- subject — put the reference / code / short claim in the Subject line.
- signoff / forward — carry it in a sign-off / title, or a forwarded-message header (provenance).
- record — paste the artifact (a system/log line, a confirmation / invoice / letter reference with
  its own date) into a body and let its data speak for itself.
- body — state it plainly. Use for the false statement (a3) and the victim's plain reliance only.
What must be PRESENT in a clue is the OBSERVABLE fact; what stays INFERRED is the conclusion — never
state that. Subtle is the goal, unreadable is the failure: the assigned fact must actually be there.

## THE FALSE STATEMENT AND RELIANCE (the a3 clue)
The clue carrying a3 is where the actor asserts the false version to the victim. If the plan attaches
the victim's reliance to this clue, make it a 2-message thread on ONE subject: message 1 = the
actor's assertion to the victim; message 2 = the victim's SHORT reply BACK TO THE ACTOR (To: the
actor, same subject).
- The victim TAKES THE ACTOR AT THEIR WORD: never questions, challenges, double-checks, or asks for
  proof of the clearance; the truth NEVER surfaces in any thread.
- Keep the reply terse and natural, the way a busy person actually fires one off — a quick "ok" plus
  what they'll do next ("ok thx, releasing it to the desk"). Do NOT mechanically REPEAT or restate
  the counterparty, the deal id, the figures, or the actor's own sentence back at them — nobody
  echoes the details they were just told. Write the reliance as a plain action, NEVER as "relying on
  your false assurance".

## EACH CLUE IS ONE CLEAN EMAIL THREAD
- A clue is ONE email, or a reply chain of <= 2 emails on the SAME subject. Never bundle two
  separate emails (a new subject, or a message to a different recipient that is not a reply in that
  same thread) into one clue.
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
{"clues":[{"i":1,"carries":["a1","a2"],"plot":"the observable scene this clue shows","messages":[{"from":"Person ?","to":["Person ?"],"cc":[],"date":"YYYY-MM-DD","subject":"...","body":"..."}]}]}
