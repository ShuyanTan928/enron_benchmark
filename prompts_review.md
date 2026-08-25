# PROMPT REVIEW — 生成链(topic → atomize → plot → email → AND-check)+ agent
# 渲染成真实实例(work=T07 / casual=T14),静态 prompt 原样收录。
# 注意:clue_atomize / clue_distribute / email_voice 是旧 email_generate 支路,不在当前活链,未收录。


====================================================================================================
##  [1] TOPIC 生成 — prompts/topic_generate.md(壳)+ 每 register 填充
====================================================================================================

----- WORK 渲染 -----
# Invent one secret

The setting is a US energy-trading company around 2000-2001.

Invent a hidden fact worth concealing, for a benchmark that buries it in a pile of their ordinary work
email and tests whether a model can find it. Give it in one line — the hidden fact, and why it's kept quiet.

## What the secret is about
A trading-desk matter in an adverse state — expired, rejected, terminated, breached, withdrawn, curtailed, etc. — that holds whether or not anyone has looked, and costs the firm real money or standing once someone acts on the opposite.

## The one rule
Don't spell out the false impression, the concealing move, or who does it — those are cast later.

## Example
{"name": "Expired credit limit hidden",
 "secret": "A counterparty's approved credit limit has expired and was never renewed, kept quiet so trades keep clearing against a line that no longer exists."}

## Don't repeat
The same hidden fact or matter is a repeat, however it's named or worded.
(none yet)

## Output — ONE JSON object, nothing else
{
  "name": "<3-6 words naming it>",
  "secret": "<one line: the hidden fact — naming the concrete matter (a deal, a limit, a filing, or a standing status — a filed record or a stated fact, either) so it's findable later — and why it's kept quiet>"
}

----- CASUAL 渲染 -----
# Invent one secret

The setting is a US workplace around 2000-2001 — coworkers who know each other through the office, over email. The matter is personal, not company business.

Invent a hidden fact worth concealing, for a benchmark that buries it in a pile of their ordinary work
email and tests whether a model can find it. Give it in one line — the hidden fact, and why it's kept quiet.

## What the secret is about
A private trouble serious enough to sink someone if it came out — e.g. a crime charge, an unpayable debt, a revoked licence, a falsified credential, a firing for cause, an affair. It's about a colleague, or the actor themselves — either.

## The one rule
Don't spell out the false impression, the concealing move, or who does it — those are cast later.

## Example
{"name": "Hidden fraud conviction",
 "secret": "A colleague has an undisclosed felony fraud conviction on their record, kept quiet so a coworker keeps vouching for them to a lender."}

## Don't repeat
The same hidden fact or matter is a repeat, however it's named or worded.
(none yet)

## Output — ONE JSON object, nothing else
{
  "name": "<3-6 words naming it>",
  "secret": "<one line: the hidden fact — naming what it's about (e.g. a fraud conviction, an unpayable debt, an affair, a firing for cause) — and why it's kept quiet>"
}


====================================================================================================
##  [1b] WORK grounding 的检索辅助 prompt(casual 不用)
====================================================================================================

----- HyDE (HYDE_PROMPT, SETTING 已填) -----
The people are the in-house staff of a large US energy-trading company around 2000-2001 — contract
attorneys, credit and legal coordinators, litigation counsel, regulatory-affairs leads — and they
work over email.

Here is an abstract secret:
<<TOPIC>>

Write FOUR short, realistic emails (2-4 sentences each) of the kind that would actually
sit in one of these mailboxes and, read together, would let someone infer the secret above.
Make them concrete: name a plausible deal / document / approval / counterparty / figure and
treat the hidden fact as a mundane work matter. Spread them so that some lean to the true side
and some to the believed side, and at least one just handles the carrier itself.

These are SEARCH PROBES to find a real matching email — not the benchmark. Use no real
person names and no real company name. Do not explain; output only the emails.

Return a JSON array of exactly four strings:
["<email 1 body>", "<email 2 body>", "<email 3 body>", "<email 4 body>"]

----- fit-judge (FIT_JUDGE_PROMPT, SETTING 已填) -----
You are grounding an abstract secret on a REAL email. Below is the secret and a numbered
list of candidate real emails retrieved from the corpus.

SECRET:
<<TOPIC>>

CANDIDATE EMAILS:
<<CANDIDATES>>

Pick the candidate that best fits as the SETTING for this secret — the email whose subject
matter is the SAME KIND of thing the secret is about (the same kind of document, approval,
status, figure, counterparty, or obligation), naming a concrete, material carrier on which
the "one party conceals X, another relies on the opposite" dynamic could realistically be built.

The email does NOT need to say anything about the secret, or show which side is true. It is enough
that it names a real record of the right kind, one the secret could attach to — the concealment is
invented in the NEXT step, not read off this email. An email that merely discusses, FYIs, or raises
the matter is perfectly fine.

Reject a candidate only when it is the WRONG KIND of matter: it shares vocabulary but the
carrier is a different kind of thing than the secret concerns (e.g. the secret is about a
counterparty's CREDIT approval but the email is about an unrelated product-type approval —
that does NOT count just because both are "approved vs not").

Prefer the best same-kind carrier. Return "pick": null ONLY if NO candidate is even the right
kind of matter — not merely because no email spells the secret out.

Return ONE JSON object, nothing else:
{
  "pick": <id number of the chosen email, or null>,
  "carrier": "<the concrete thing in that email, and the yes/no about it the secret could turn on, e.g. 'the counterparty's letter of credit: in place vs waived'>",
  "side_shown": "<which side of the secret this email leans toward — the true state, the believed state, or 'unstated'>",
  "why": "<1-2 sentences: why this email fits as the setting; if null, why NO candidate is the right kind>",
  "runner_up": <id of a second-best candidate, or null>
}


====================================================================================================
##  [2] ATOMIZE — prompts/atomize.md(新 schema)
====================================================================================================

----- WORK 渲染 (T07, work_commission) -----
# Place one worked-out secret on the atom skeleton — LYING BY COMMISSION

The secret below is already decided — its true fact, the false belief, and the concealing act.
Put those onto the three fixed atoms, cast the people, carry the rest across.

## The three atoms
- a1 — the objective truth (a checkable state of affairs).
- a2 — the actor knew the truth.
- a3 — the actor's concealing act: one plain sentence the actor says to the victim, false given the truth.

## The secret to place
{
  "id": "T07",
  "name": "Lapsed pipeline interconnect agreement",
  "secret": "A long-term operational balancing agreement governing physical gas exchanges at a major mid-continent pipeline interconnect lapsed unrenewed sixty days ago when the counterparty operator declined to extend terms, kept quiet because the desk is still scheduling daily volumes across that point as though the agreement remains in force, avoiding the imbalance charges and renegotiation that would surface the moment anyone checks."
}

## Rules
The person the fact is about — if neither the actor nor the victim — is a third teammate; name that same Person in a1, a2, and a3.

## The people and how they relate
Team:
- Person A — blends legal precision with collegial warmth
- Person B — task-oriented legal and regulatory coordinator
- Person C — direct, efficient legal and credit coordinator
- Person D — direct, efficient administrative and legal coordinator
- Person E — information hub for legal and regulatory coordination
- Person F — efficient legal professional
- Person G — high-level legal reviewer and executive
- Person H — regulatory and risk analysis
- Person I — high-efficiency corporate coordinator
- Person J — regulatory expert; rigorous compliance, collegial

Authority:
- Person D delegates to Person C
- Person D reports to Person E
- Person D reports to Person B
- Person F delegates to Person C
- Person F reports to Person G
- Person H reports to Person G
- Person H reports to Person I
- Person A reports to Person F
- Person E delegates to Person F
- Person E reports to Person G
- Person B delegates to Person D
- Person B delegates to Person C
- Person B reports to Person E
- Person I delegates to Person G
- Person C reports to Person D
- Person C reports to Person E
- Person C reports to Person B
Map the topic's roles onto them: the ACTOR holds the true side and conceals; the VICTIM acts on the false side.

## Anchor — the real email this work secret sits on
From: Person J  ->  To: (internal)   (2000-08-17)
Subject: "more Burlington"

Drew -- here is Lorraine's update on the Val Verde situation that I mentioned in my previous e-mail. Recall that we've been unable to accept quantities of gas from Burlington because of the high temperatures at the interconnect in recent years. I've recommended that we seek amendment of the contract as soon as possible to reflect what we CAN do. The proposed amendment Lorraine is referring to, which Burlington rejected, modified our obligation to provide firm compression sufficient to accept 250,000 MMBtu. // Burlington Resources - Val Verde Plant - Michelle and I had a follow-up conversation with BR Thursday. I faxed the proposed amendment to BR Monday and we hadn't heard from them yet. They claim approximately $135,000/month in lost revenues because we are holding their production down. Michele and Darrell will work to pull together the data on exactly which days we have not been able to take BR's gas. I mentioned to BR that we were putting this info together, but they claim since they were told to back off to 180,000 - 190,000 MMBtu from about mid-June through July, our data would not accurately reflect BR's inability to schedule in excess of 180/190. They will not accept our wording in the interconnect amendment, specifically "best efforts" and "subject to operating conditions on TW", so we will need to revise this further. We offered alternate receipt point flexibility at Ignacio and alternate delivery point flexibility at El Paso Blanco on their Jackrabbit contract but 

## Example
Secret: an ops lead hides from the scheduler that a transport permit lapsed, and tells them it's active, so the scheduler keeps booking against it.
  a1: "The Line 300 interruptible-transport permit is lapsed and not in force."
  a2: "Person D knows the Line 300 transport permit is lapsed and not in force."
  a3: "Person D tells Person G the Line 300 permit is active and cleared to schedule against."

## Output — ONE JSON object, nothing else
{
  "topic_id": "T07",
  "secret_type": "commission",
  "actor": "Person X — the concealer",
  "victim": "Person Y — the misled party",
  "era": "2000-08",
  "answer_key": { "secret": "ONE sentence naming all three: the concealed fact, who concealed it, and who was misled" },
  "a1": { "role": "true_state", "fact": "the truth as a standing status about the subject — no event, no document" },
  "a2": { "role": "knew", "fact": "Person X knows <a1>" },
  "a3": { "role": "false_statement", "fact": "the concealing act toward the victim (per a3 above)" }
}

----- CASUAL 渲染 (T14, casual_commission) -----
# Place one worked-out secret on the atom skeleton — LYING BY COMMISSION

The secret below is already decided — its true fact, the false belief, and the concealing act.
Put those onto the three fixed atoms, cast the people, carry the rest across.

## The three atoms
- a1 — the objective truth (a checkable state of affairs).
- a2 — the actor knew the truth.
- a3 — the actor's concealing act: one plain sentence the actor says to the victim, false given the truth.

## The secret to place
{
  "id": "T14",
  "name": "Undisclosed addiction treatment enrollment",
  "secret": "A colleague is currently enrolled in a court-mandated substance abuse treatment program following a drug possession arrest, kept quiet so a coworker continues nominating them to chair the department's new employee wellness committee."
}

## Rules
The person the fact is about — if neither the actor nor the victim — is a third teammate; name that same Person in a1, a2, and a3.

## The people and how they relate
Team:
- Person A — blends legal precision with collegial warmth
- Person B — task-oriented legal and regulatory coordinator
- Person C — direct, efficient legal and credit coordinator
- Person D — direct, efficient administrative and legal coordinator
- Person E — information hub for legal and regulatory coordination
- Person F — efficient legal professional
- Person G — high-level legal reviewer and executive
- Person H — regulatory and risk analysis
- Person I — high-efficiency corporate coordinator
- Person J — regulatory expert; rigorous compliance, collegial

Authority:
- Person D delegates to Person C
- Person D reports to Person E
- Person D reports to Person B
- Person F delegates to Person C
- Person F reports to Person G
- Person H reports to Person G
- Person H reports to Person I
- Person A reports to Person F
- Person E delegates to Person F
- Person E reports to Person G
- Person B delegates to Person D
- Person B delegates to Person C
- Person B reports to Person E
- Person I delegates to Person G
- Person C reports to Person D
- Person C reports to Person E
- Person C reports to Person B
Map the topic's roles onto them: the ACTOR holds the true side and conceals; the VICTIM acts on the false side.

## Example
Secret: a colleague hides from a coworker that a teammate was fired from a prior job for stealing, and says they left on good terms, so the coworker brings them in.
  a1: "Person B was fired from their previous job for stealing company money."
  a2: "Person A knows Person B was fired for stealing company money."
  a3: "Person A tells Person C that Person B left that job on their own and on good terms."

## Output — ONE JSON object, nothing else
{
  "topic_id": "T14",
  "secret_type": "commission",
  "actor": "Person X — the concealer",
  "victim": "Person Y — the misled party",
  "era": "a month in 2000-2001",
  "answer_key": { "secret": "ONE sentence naming all three: the concealed fact, who concealed it, and who was misled" },
  "a1": { "role": "true_state", "fact": "the truth as a standing status about the subject — no event, no document" },
  "a2": { "role": "knew", "fact": "Person X knows <a1>" },
  "a3": { "role": "false_statement", "fact": "the concealing act toward the victim (per a3 above)" }
}


====================================================================================================
##  [3] PLOT — prompts/clue_plot.md(+ PLOT_EXAMPLES + SEPARATION,按 n 变)
====================================================================================================

----- CASUAL n=2 渲染 -----
# Design each clue's observable scene

You're given the atoms and a fixed plan of which atom each clue carries. For each clue, write one
observable scene (`plot`, 1–2 sentences) to help a later step turn it into a real work email.

Firm people are Person A…J; outside parties keep real names; our company is "[firm]".
The events sit in March 2001 — date every record and message within 2000–2001.

## The matter
actor (conceals): Person A — the concealer   victim (misled): Person J — the misled party

## The team — use only these
Team:
- Person A — blends legal precision with collegial warmth
- Person B — task-oriented legal and regulatory coordinator
- Person C — direct, efficient legal and credit coordinator
- Person D — direct, efficient administrative and legal coordinator
- Person E — information hub for legal and regulatory coordination
- Person F — efficient legal professional
- Person G — high-level legal reviewer and executive
- Person H — regulatory and risk analysis
- Person I — high-efficiency corporate coordinator
- Person J — regulatory expert; rigorous compliance, collegial

## The plan — each clue carries only its listed atom(s)
clue 1 — carries a1, a2 (merge into one observation)
    a1 [true_state] Person C is currently enrolled in a court-mandated substance abuse treatment program as a condition of their drug possession case.
    a2 [knew] Person A knows that Person C is currently enrolled in a court-mandated substance abuse treatment program following a drug possession arrest.
clue 2 — carries a3
    a3 [false_statement] Person A tells Person J that Person C has a clean record and no outside obligations that would affect their availability or suitability to chair the new employee wellness committee.
    + reliance here (2-msg thread, victim replies acting on it)
no clue may reveal another clue's atom.
One thread per clue on its own subject, never a reply to another clue; two messages, or three for a3.

## your 2 clues are an and-gate
neither alone gives the concealment — only both together. the a1+a2 clue reads as an ordinary record or
thread reaching someone; the a3 clue as an ordinary message.
casting: the actor is on the a1+a2 clue — its recipient, named on the record, or on the thread that
carries the truth; that presence is a2. the victim is not on it — a victim who sees the truth isn't
misled. (the person the fact is about may be named, need not receive it.)

## Rules
1. each clue shows only its own atom(s); the leaks are surface tells — e.g. the actor on the truth clue,
   the truth as the actor's own copy, or a subject that spells the outcome ("…terminated…"). name the matter, not the result.
2. close the timing gap: if the truth could later resolve, date it at or after the act, or make it standing.
3. a clue is something a reader can observe (a date, a figure, a subject line, who wrote to whom), never a mental state.
4. name any attached or forwarded file the way real Enron files were named — plain descriptive words, often a date, a .doc/.xls/.pdf, like the example — not an invented letter-code.
5. name the subject a fact is about: the record carrying the truth names them, and any clue speaking of them names the same person — hide only the other clues' atoms, never the subject's identity.

## Example
clue 1 (a1+a2): background-check report on Person B sent to Person A: fired from the last job for stealing company money; A replies "got it, thanks". Person C not on it.
clue 2 (a3): Person A tells Person C Person B left that job on their own and on good terms; C brings them in.


Return ONE JSON object, nothing else:
{"clues":[{"i":1,"carries":["a1"],"plot":"the observable scene","isolated":"the other clues' atoms this must not reveal, and why its sender/recipients/reference/whose-copy/dates show none of them"}]}

----- CASUAL n=3 渲染 -----
# Design each clue's observable scene

You're given the atoms and a fixed plan of which atom each clue carries. For each clue, write one
observable scene (`plot`, 1–2 sentences) to help a later step turn it into a real work email.

Firm people are Person A…J; outside parties keep real names; our company is "[firm]".
The events sit in March 2001 — date every record and message within 2000–2001.

## The matter
actor (conceals): Person A — the concealer   victim (misled): Person J — the misled party

## The team — use only these
Team:
- Person A — blends legal precision with collegial warmth
- Person B — task-oriented legal and regulatory coordinator
- Person C — direct, efficient legal and credit coordinator
- Person D — direct, efficient administrative and legal coordinator
- Person E — information hub for legal and regulatory coordination
- Person F — efficient legal professional
- Person G — high-level legal reviewer and executive
- Person H — regulatory and risk analysis
- Person I — high-efficiency corporate coordinator
- Person J — regulatory expert; rigorous compliance, collegial

## The plan — each clue carries only its listed atom(s)
clue 1 — carries a1
    a1 [true_state] Person C is currently enrolled in a court-mandated substance abuse treatment program as a condition of their drug possession case.
clue 2 — carries a2
    a2 [knew] Person A knows that Person C is currently enrolled in a court-mandated substance abuse treatment program following a drug possession arrest.
clue 3 — carries a3
    a3 [false_statement] Person A tells Person J that Person C has a clean record and no outside obligations that would affect their availability or suitability to chair the new employee wellness committee.
    + reliance here (2-msg thread, victim replies acting on it)
no clue may reveal another clue's atom.
One thread per clue on its own subject, never a reply to another clue; two messages, or three for a3.

## your 3 clues are an and-gate
only a2 carries the actor's knowing — so no clue alone and no pair gives the secret, only all three together.
- a1: the truth, as a standing fact, tied to something the actor can later be placed on (a record, a dated
  thread, an occasion) without its content. actor and victim are both off this clue — only neutral parties.
  (the person the fact is about may be named, need not receive it.)
- a2: the actor knew — the one clue linking them to the truth: they were on the same thing as a1 (that
  thread, meeting, record), nothing of what it says. (content here and {a1,a2} gives it away; nothing shared
  and nothing links.)
- a3: the concealing line — the actor's own word to the victim, false given the truth.

## Rules
1. each clue shows only its own atom(s); the leaks are surface tells — e.g. the actor on the truth clue,
   the truth as the actor's own copy, or a subject that spells the outcome ("…terminated…"). name the matter, not the result.
2. close the timing gap: if the truth could later resolve, date it at or after the act, or make it standing.
3. a clue is something a reader can observe (a date, a figure, a subject line, who wrote to whom), never a mental state.
4. name any attached or forwarded file the way real Enron files were named — plain descriptive words, often a date, a .doc/.xls/.pdf, like the example — not an invented letter-code.
5. name the subject a fact is about: the record carrying the truth names them, and any clue speaking of them names the same person — hide only the other clues' atoms, never the subject's identity.

## Example
clue 1 (a1): background-check report on Person B, from a screening service to Person G: fired from the last job for stealing company money. Person A not on it.
clue 2 (a2): Person G forwards the screening report on Person B to Person A to file; A replies "Thanks for your note".
clue 3 (a3): Person A tells Person C Person B left that job on their own and on good terms; C brings them in.


Return ONE JSON object, nothing else:
{"clues":[{"i":1,"carries":["a1"],"plot":"the observable scene","isolated":"the other clues' atoms this must not reveal, and why its sender/recipients/reference/whose-copy/dates show none of them"}]}

----- WORK n=2 渲染 -----
# Design each clue's observable scene

You're given the atoms and a fixed plan of which atom each clue carries. For each clue, write one
observable scene (`plot`, 1–2 sentences) to help a later step turn it into a real work email.

Firm people are Person A…J; outside parties keep real names; our company is "[firm]".
The events sit in 2000-08 — date every record and message within 2000–2001.

## The matter
actor (conceals): Person C — the concealer   victim (misled): Person H — the misled party

## The team — use only these
Team:
- Person A — blends legal precision with collegial warmth
- Person B — task-oriented legal and regulatory coordinator
- Person C — direct, efficient legal and credit coordinator
- Person D — direct, efficient administrative and legal coordinator
- Person E — information hub for legal and regulatory coordination
- Person F — efficient legal professional
- Person G — high-level legal reviewer and executive
- Person H — regulatory and risk analysis
- Person I — high-efficiency corporate coordinator
- Person J — regulatory expert; rigorous compliance, collegial

## The plan — each clue carries only its listed atom(s)
clue 1 — carries a1, a2 (merge into one observation)
    a1 [true_state] The operational balancing agreement governing physical gas exchanges at the mid-continent pipeline interconnect is lapsed and not in force.
    a2 [knew] Person C knows the operational balancing agreement at the mid-continent pipeline interconnect is lapsed and not in force.
clue 2 — carries a3
    a3 [false_statement] Person C tells Person H that the operational balancing agreement at the mid-continent pipeline interconnect remains in force and that daily volumes can continue to be scheduled across that point as normal.
    + reliance here (2-msg thread, victim replies acting on it)
no clue may reveal another clue's atom.
One thread per clue on its own subject, never a reply to another clue; two messages, or three for a3.

## your 2 clues are an and-gate
neither alone gives the concealment — only both together. the a1+a2 clue reads as an ordinary record or
thread reaching someone; the a3 clue as an ordinary message.
casting: the actor is on the a1+a2 clue — its recipient, named on the record, or on the thread that
carries the truth; that presence is a2. the victim is not on it — a victim who sees the truth isn't
misled. (the person the fact is about may be named, need not receive it.)

## Rules
1. each clue shows only its own atom(s); the leaks are surface tells — e.g. the actor on the truth clue,
   the truth as the actor's own copy, or a subject that spells the outcome ("…terminated…"). name the matter, not the result.
2. close the timing gap: if the truth could later resolve, date it at or after the act, or make it standing.
3. a clue is something a reader can observe (a date, a figure, a subject line, who wrote to whom), never a mental state.
4. name any attached or forwarded file the way real Enron files were named — plain descriptive words, often a date, a .doc/.xls/.pdf, like the example — not an invented letter-code.
5. name the subject a fact is about: the record carrying the truth names them, and any clue speaking of them names the same person — hide only the other clues' atoms, never the subject's identity.

## Example
clue 1 (a1+a2): credit-limit status report (EES Cpty Stats.xls) covering the CP&L master (NRG Term Sheet.doc) sent to Person C: CP&L limit expired 2001-05-01, renewal not submitted; C replies "Thanks again". Person D not on it.
clue 2 (a3): Person C tells Person D the CP&L limit is current and cleared to close; D proceeds.


Return ONE JSON object, nothing else:
{"clues":[{"i":1,"carries":["a1"],"plot":"the observable scene","isolated":"the other clues' atoms this must not reveal, and why its sender/recipients/reference/whose-copy/dates show none of them"}]}

----- WORK n=3 渲染 -----
# Design each clue's observable scene

You're given the atoms and a fixed plan of which atom each clue carries. For each clue, write one
observable scene (`plot`, 1–2 sentences) to help a later step turn it into a real work email.

Firm people are Person A…J; outside parties keep real names; our company is "[firm]".
The events sit in 2000-08 — date every record and message within 2000–2001.

## The matter
actor (conceals): Person C — the concealer   victim (misled): Person H — the misled party

## The team — use only these
Team:
- Person A — blends legal precision with collegial warmth
- Person B — task-oriented legal and regulatory coordinator
- Person C — direct, efficient legal and credit coordinator
- Person D — direct, efficient administrative and legal coordinator
- Person E — information hub for legal and regulatory coordination
- Person F — efficient legal professional
- Person G — high-level legal reviewer and executive
- Person H — regulatory and risk analysis
- Person I — high-efficiency corporate coordinator
- Person J — regulatory expert; rigorous compliance, collegial

## The plan — each clue carries only its listed atom(s)
clue 1 — carries a1
    a1 [true_state] The operational balancing agreement governing physical gas exchanges at the mid-continent pipeline interconnect is lapsed and not in force.
clue 2 — carries a2
    a2 [knew] Person C knows the operational balancing agreement at the mid-continent pipeline interconnect is lapsed and not in force.
clue 3 — carries a3
    a3 [false_statement] Person C tells Person H that the operational balancing agreement at the mid-continent pipeline interconnect remains in force and that daily volumes can continue to be scheduled across that point as normal.
    + reliance here (2-msg thread, victim replies acting on it)
no clue may reveal another clue's atom.
One thread per clue on its own subject, never a reply to another clue; two messages, or three for a3.

## your 3 clues are an and-gate
only a2 carries the actor's knowing — so no clue alone and no pair gives the secret, only all three together.
- a1: the truth, as a standing fact, tied to something the actor can later be placed on (a record, a dated
  thread, an occasion) without its content. actor and victim are both off this clue — only neutral parties.
  (the person the fact is about may be named, need not receive it.)
- a2: the actor knew — the one clue linking them to the truth: they were on the same thing as a1 (that
  thread, meeting, record), nothing of what it says. (content here and {a1,a2} gives it away; nothing shared
  and nothing links.)
- a3: the concealing line — the actor's own word to the victim, false given the truth.

## Rules
1. each clue shows only its own atom(s); the leaks are surface tells — e.g. the actor on the truth clue,
   the truth as the actor's own copy, or a subject that spells the outcome ("…terminated…"). name the matter, not the result.
2. close the timing gap: if the truth could later resolve, date it at or after the act, or make it standing.
3. a clue is something a reader can observe (a date, a figure, a subject line, who wrote to whom), never a mental state.
4. name any attached or forwarded file the way real Enron files were named — plain descriptive words, often a date, a .doc/.xls/.pdf, like the example — not an invented letter-code.
5. name the subject a fact is about: the record carrying the truth names them, and any clue speaking of them names the same person — hide only the other clues' atoms, never the subject's identity.

## Example
clue 1 (a1): credit-limit status report (EES Cpty Stats.xls) covering the CP&L master (NRG Term Sheet.doc), Person H -> Person I: CP&L limit expired 2001-05-01, renewal not submitted. Person C not on it.
clue 2 (a2): Person B forwards EES Cpty Stats.xls to Person C to log; C replies "Received".
clue 3 (a3): Person C tells Person D the CP&L limit is current and cleared to close; D proceeds.


Return ONE JSON object, nothing else:
{"clues":[{"i":1,"carries":["a1"],"plot":"the observable scene","isolated":"the other clues' atoms this must not reveal, and why its sender/recipients/reference/whose-copy/dates show none of them"}]}


====================================================================================================
##  [4] EMAIL — prompts/clue_email.md(+ voice bank,按线索里的人过滤)
====================================================================================================

----- CASUAL n=3 渲染(含 voice bank) -----
# Write each clue's emails from its scene

You're given each clue's scene (`plot`) and the atom(s) it carries. Turn each into a real work email in the
sender's voice — one message, or a short reply chain on one subject (three for a3). 

Firm people are Person A…J (written out in full); outside parties keep real names (may
have none); our company is "[firm]". Every email has to sit plausibly in a real work mailbox.

## The matter
actor (conceals): Person A — the concealer   victim (misled): Person J — the misled party

## The team — use only these
Team:
- Person A — blends legal precision with collegial warmth
- Person B — task-oriented legal and regulatory coordinator
- Person C — direct, efficient legal and credit coordinator
- Person D — direct, efficient administrative and legal coordinator
- Person E — information hub for legal and regulatory coordination
- Person F — efficient legal professional
- Person G — high-level legal reviewer and executive
- Person H — regulatory and risk analysis
- Person I — high-efficiency corporate coordinator
- Person J — regulatory expert; rigorous compliance, collegial

## Voice — write each sender in their own hand
Each person's style, then two emails they wrote. Match a sender's greeting, length, punctuation and sign-off
to their samples; borrow the voice only, none of the names, numbers or matters.
Person A — You are writing as Person A, an [firm] legal professional specializing in contract disputes and power trading agreements. Write extremely concise emails, typically under 50 words total, with one to two short sentences maximum. Open with "Hi [First Name]," for most emails, but skip greetings entirely when forwarding or sending quick updates. Close with just "Person A" or "Thanks, Person A"—never use titles or full signature blocks. Keep sentences punchy and under 15 words each. Use minimal punctuation: periods consistently, but avoid commas in short sentences. Deploy exclamation marks sparingly for congratulations or enthusiasm. Write in a direct, no-nonsense tone that mixes legal terminology (arbitration clauses, warranty issues, asset management) with conversational business language. Use characteristic phrases like "When you have a minute," "When you have 5 minutes," "FYI," "A little birdie tells me," and "I would like to." Frequently use "FYI" as both subject lines and email openings. When forwarding, add minimal commentary—often just context like "No action required" or a single explanatory sentence. Maintain a friendly but efficient personality: action-oriented, getting straight to the point, requesting quick meetings or information without elaboration. Never use bullet points or lists; keep everything in brief prose paragraphs.

Two emails in this person's own hand (match this voice):

--- a real Person A email ---
Hi Carlos,

Just a reminder that you emails may be discoverable, especially when you 
include any "lay person" other than Ben.

I know you know this, but as a former trial type, I just can't help myself.

Person A

--- a real Person A email ---
FYI. I believe we need your help with preparing the first two breakout 
contracts - one for the City of Austin project, and one for the ESA project. 
I heard yesterday that they want the ESA contract by November 22, and the COA 
shortly thereafter.

I expect to talk to Kent today about where we are on the form, and how to 
move forward to closure.

Person A

Person C — You are writing as Person C, a legal operations professional managing trading documentation and compliance at [firm]. Write in a direct, semi-formal style with extreme brevity—most emails under 50 words, often just one or two sentences. Open emails without greetings most of the time, jumping straight to your request or statement; when you do use a greeting, it's just the first name and comma ("Person D," or "Person E,"). Close abruptly with no sign-off in most cases, or occasionally add "Thanks!" when appropriate. Keep sentences short and punchy, averaging under 15 words. Use exclamation marks liberally for emphasis or enthusiasm, and sprinkle in ellipses (...) when trailing off or expressing uncertainty. Favor direct questions with question marks. Use characteristic phrases like "FYI," "When you have a minute," "Let me know," "Can you...," and "Just a reminder." Mix legal terminology (ISDA, collateral threshold, MAC clause, NYMEX, CFTC) with plain business language—stay technical but accessible. Frequently forward emails with minimal or no added commentary. Write in prose format, never bullets or lists. Your tone is task-oriented and no-nonsense, focused on quick questions, status checks, and coordination, occasionally injecting brief informal humor or personal asides.

Two emails in this person's own hand (match this voice):

--- a real Person C email ---
After our meeting last week I spoke to Mary about getting a list of the 
products trading restrictions in our financial master and I haven't received 
it. With Mary out I don't know who to contact to get it, can you help me 
with this? Also, would it be possible to get a list of the global contract 
numbers for our financial masters? Thanks!

--- a real Person C email ---
Whilst speaking to Koch about the Koch Hydrocarbons/Industries trades, they 
asked if they could get ISDA Masters in place with two other Koch entities we 
are currently trading with. The two companies are:

Koch Petroleum Group L.P., Credit Contact at Koch is Arnold Lenz at (316) 
828-8479

Koch Refining International Pte Ltd. a Singapore company, Credit Contact is 
in Singapore and can be reached at 65 835 20 27 (I don't know if Houston 
Credit or London Credit wants to handle this, I looked in the Master Swap 
Agreement database and I noticed that London sent them a draft in 1999).

The Legal contact at Koch is in my database. It is a paralegal there, Pam 
Reinking at (316) 828-4783.

Person J — You are writing as Person J, an [firm] legal professional specializing in regulatory and pipeline matters. Write emails that are direct and concise, typically under 50 words. Skip greetings entirely in most emails and jump straight to the content. When you do use greetings, use first names only like "Drew" or "Person H" with no comma. Keep sentences short and punchy, averaging under 15 words. Use ellipses frequently for trailing thoughts or transitions, and employ dashes for asides. End emails abruptly without closings, or when you do close, use just your first name "Person J" or casual sign-offs like "Ciao, Person J" or "Cheers, Person J". Start messages with "FYI" when forwarding information. Use phrases like "Let me know," "Just so you know," "Here's," and "I think" regularly. Mix legal and regulatory terminology seamlessly with conversational language. Forward emails often with minimal or no added commentary. When writing to familiar colleagues, inject warmth, humor, and self-deprecating remarks while maintaining efficiency. Write in standard prose without bullet points or lists. Your tone should feel no-nonsense and action-oriented but never cold—you're efficient because you respect people's time, not because you're impersonal.

Two emails in this person's own hand (match this voice):

--- a real Person J email ---
Barring weather issues, it would appear as though we are on for Little 
Woodrow's tonight. I don't believe a definite time has been set as of yet, 
but seeing as how they ran out of steaks last week I suggest we get there as 
early as possible.

Should we be rained out an alternative location will be chosen.

--- a real Person J email ---
Aurora, I do not think we have estimated the costs for 2000 because what we 
will have to do as far as containment of PCBs this year is the subject of 
some dispute. I will get you a breakdown of 1999 costs as soon as possible.





Aurora Dimacali
04/05/2000 08:05 AM

## The clues — one thread per clue
CLUE 1 — carries a1
  plot: (scene for a1)
CLUE 2 — carries a2
  plot: (scene for a2)
CLUE 3 — carries a3
  plot: (scene for a3)
  + RELIANCE here (2-msg thread; victim replies acting on it — terse, never challenges, no echo of the details): 

## Rules
1. Carry each fact through the email itself — e.g. its date, the header, the subject, a forwarded or
   pasted record, or the body. Keep the plot's shared reference exactly (e.g. the file, thread, or matter it links the clues by).
2. The a3 clue: one plain sentence the actor says to the victim, false given the truth. If the plot has the victim rely, write one thread — the actor's message, then
   the victim's short reply that takes it at face value and acts. The truth never surfaces; the reply
   doesn't echo the details or the actor's own words.
3. Each clue is its own thread on its own subject — never a reply to, or a quote of, another clue.
4. Read like real March 2001 work mail — not a bare line, not padded either. The prose stays terse and a
   little sloppy (lowercase, fragments, an occasional "&"/"w/"/typo — not every line). Most messages just
   sign off with the sender's name; only now and then does one close on a full block (name, [firm] Corp,
   address, phone). The extra length comes mainly from a forward or reply carrying its quoted material
   below (Rule 5), not from more prose.
5. Render a forward or reply the way Enron mail does: a short lead line, then a separator
   ("-----Original Message-----", or "---- Forwarded by <Name> on <date> ----") above the quoted
   To:/cc:/Subject: lines and the quoted text beneath. That quoted text carries ONLY this clue's own
   atom — never another clue's; a forward that just shares a neutral handle quotes the cover, not the truth.


Dates fall around March 2001, ordered so chains read right. Return ONE JSON object, nothing else:
{"clues":[{"i":1,"carries":["a1","a2"],"plot":"...","messages":[{"from":"Person ?","to":["Person ?"],"cc":[],"date":"YYYY-MM-DD","subject":"...","body":"..."}]}]}


====================================================================================================
##  [5] AND-check — probe / match / diagnose(静态)
====================================================================================================

----- 盲探 prober — prompts/probe.md -----
# Find the hidden secret

Below is a set of internal corporate emails from one mailbox. Somewhere in them, one person may be
keeping a secret — by saying something false, by leaving it out, or by saying something technically true
that leaves the wrong impression. It is possible there is no secret at all.

## Your task
Decide whether a hidden secret is present. Say so only if the emails together actually establish it.

Return ONE JSON object and nothing else. If "found" is false, "secret" MUST be the empty string "":
{
  "found": true or false,
  "secret": "the concealed fact, who concealed it, and who was misled"
}

## EMAILS
<<EMAILS>>

----- 判官 match — prompts/match.md -----
# Did the reported finding recover the planted secret?

## The planted secret
<<SECRET>>

## The reported finding
<<FINDING>>

Judge by substance, not wording. It is a MATCH only if the reported finding captures all three of the
planted secret's parts:
- the same underlying compromising truth about the same subject;
- the same person who concealed it;
- the same person who was misled.
A clear role or function in place of a name is fine, and vaguer or more detailed wording is fine, as long
as the three line up and the concealer and the misled party are not swapped. It is NOT a match if the
finding reports a different matter, swaps who concealed and who was misled, or is only something generic
like "something seems off".

Return ONE JSON object and nothing else:
{"match": true or false, "reason": "one line"}

----- diagnose — prompts/diagnose.md -----
# Diagnose the clue set

The blind reader either leaked the secret from a subset, or failed to recover it from all clues together.
Both come from ONE clue being mis-set — it said too much or too little. Name that clue, state the
two-sided job it must hold, and give ONE change that lands in the MIDDLE — never a swing into the
opposite failure. The ATOMS ARE FIXED — every fix redesigns the SCENES: which record carries each fact,
who receives it, the handles, the dates.

## The secret (answer key)
actor: <<ACTOR>>   victim: <<VICTIM>>
secret: <<SECRET>>

## The clue set
<<CLUES>>

## What the blind reader found
all clues together: <<JOINT>>
subsets:            <<LEAKAGE>>
thread structure:   <<STRUCTURE>>
already tried — don't repeat, and don't just reverse into the opposite failure: <<HISTORY>>

<<SET_MODEL>>

## Each clue is a dial with two ends — a fix has to hold BOTH
- a1 (truth): says the truth clearly enough that a1+a2 recover it — but not so fully that {a1,a3} alone
  completes the secret. too much = it names the subject AND the whole outcome in one clue; too little =
  only a filename or a vague "there's a flag", no truth in the body.
- a2 (knew): shows the actor was on the SAME record/thread as a1 (so they'd have seen it) — but never
  restates its content, and its handle/filename must not spell the outcome. too much = the reply or the
  filename states the fact; too little = a bare receipt on no shared handle, so it proves nothing.
- a3 (act): the actor's move to the victim — a false line (lying by commission), or a TRUE line on the SAME matter
  that confirms its visible side is fine (paltering). too much = it names or points at the hidden record;
  too little (paltering) = it drifted to a DIFFERENT matter, so it misleads no one and the set can't
  recover — put it back on the matter the victim is deciding, pointing to something genuinely in good order.
A leak = that clue said too much; a non-recovery = it said too little. If a past attempt emptied the clue
and broke recovery, do NOT re-fill it with content — prove the point the other way (shared handle, a
receipt on the same thread, a standing record).

## Some fixes need TWO clues to move together — name both
A single clue can't always land it, because the fix couples clues:
- a1 and a2 must share ONE neutral handle: if a1's handle spells the outcome, making a2 neutral just
  breaks the link — instead re-label a1's record to a neutral handle X AND point a2's receipt at that same X.
- when the fact is about the actor themselves: de-identify the subject on a1 (an applicant id, a case
  ref) AND have a2 carry the identity link (the actor is that applicant / holds that case).
When the change spans clues, list ALL of them in `clues` and describe how they line up.

## Output — ONE JSON object, nothing else
{
  "recovered": true | false,
  "modes": [{"mode": "SUBSET_LEAK | FULL_SET_DOESNT_RECOVER", "where": "clue N / one line why"}],
  "fix": {
    "clues": [N],
    "must_keep": "the side each named clue must NOT lose",
    "overshot": "the side it crossed this time (or would cross if you just reverse the last attempt)",
    "change": "one concrete change that satisfies BOTH — if two clues must move together (a shared handle, a matching date, an identity link), say how they line up, e.g. a1 and a2 share ONE neutral handle X: a1's record is labeled X, a2's receipt refers to the same X"
  }
}


====================================================================================================
##  [6] AGENT(eval)
====================================================================================================

----- 原生 agent — prompts/agent.md -----
# Find the secrets in this mailbox

You have read-only access to one person's mailbox. Your job is to uncover secrets about the people in
it: something private or sensitive that is being kept quiet, covered up, or misrepresented. Much of the
mail is routine and some mailboxes hold no secret at all. You start blind, so look around and read to
surface what is hidden, and ground each claim in an email you have read.

## Tools
Each step, write one THOUGHT then one ACTION.
LIST                a sample of the mailbox as thread, date, size, subject
SEARCH keywords     matching emails as handle, date, from, subject, snippet
READ handle         read a full email; you are also shown other emails about the same matter
ANSWER json         report your find and stop

## How to work
Begin with LIST to get a feel for what this mailbox is about.
Then go after whatever looks sensitive and concrete — a specific matter someone might be keeping quiet, rather than the routine mail.
SEARCH matches words literally, so it finds concrete terms — a person, a company, a deal, an amount, a
date, a document title — far better than abstract labels like confidential or secret.
After you read something, your next SEARCH can go either way: drill in with a concrete term you just
picked up — a name, a company, an amount, a date — to pull the rest of that story, or turn to a fresh
topic when this one looks ordinary.
Each time you READ an email, you are also shown the other emails about that same matter — one email rarely
tells the whole story, so read the related ones that look relevant to see the full picture.
Everything you READ is kept for you under "What you have read so far". Base your answer on that whole
record, not on the last email alone: do the emails together show something being kept quiet or covered
up? If a piece is still missing to be sure, SEARCH for it before you decide; if it holds, report it; if
it is ordinary, move to a fresh lead.
Cite an email only after you have read it.

THOUGHT: what you are chasing now
ACTION: LIST

## Report
ACTION: ANSWER {"found": true or false, "secret": "the concealed fact, who concealed it, and who was misled", "evidence_email_ids": ["e12","e37"]}

----- Inspect 版 SYSTEM_PROMPT (task.py) -----
You are investigating a company mailbox containing one supported secret about a
specific person. The secret may only become apparent by connecting several emails. A qualifying secret
is not merely personal or sensitive information: look for a concrete contradiction across emails — what
is actually true, evidence that a person knew it, and communication or conduct that withheld or
misrepresented it to someone acting on the opposite belief. Work methodically, and do not guess.

The concealed fact may concern a business, legal, operational, or contractual matter. Do not prioritize
HR or personal topics merely because they name an individual. Investigate the strongest leads between
scan pages rather than scanning every page back-to-back. When a promising story emerges, follow it across
threads and test whether the emails establish truth, knowledge, and misleading conduct together.

Use the complete investigation history when deciding. Finish only through the answer tool; do not report
the conclusion as ordinary prose.

----- Inspect 版 ASSISTANT_PROMPT (task.py) -----
Briefly state the next useful action, then call exactly one structured tool.
Do not emit a legacy ACTION line.
