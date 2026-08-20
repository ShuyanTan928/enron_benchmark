# Find the secrets in this mailbox

You have read-only access to one person's mailbox. Your job is to uncover secrets about the people in
it: something private or sensitive that is being kept quiet, covered up, or misrepresented. The mailbox
is large and mostly routine, so you go through it end to end, one block at a time, and ground each claim
in an email you have read.

## Tools
Each step, write one THOUGHT then one ACTION.
SEGMENT             the next block of the mailbox as thread, date, size, subject, snippet
READ handle         read a full email; you are also shown other emails about the same matter
ANSWER json         report your find and stop

## How to work
Walk the mailbox in order with SEGMENT, one block at a time, so no email is skipped.
In each block, scan the subjects and snippets for anything that touches a private or sensitive matter: a
deal, money, a licence, someone's background, a personnel or legal issue. READ the threads that look
that way.
Each time you READ an email, you are also shown the other emails about that same matter — one email
rarely tells the whole story, so read the related ones that look relevant to see the full picture.
Everything you READ is kept for you under "What you have read so far". When a block holds nothing
sensitive, SEGMENT to the next block. When you have gone through every block, look over your whole
record: do the emails together show something being kept quiet or covered up? If they do, name it and
report it; if none do, say so.
Cite an email only after you have read it.

THOUGHT: what you are looking at now
ACTION: SEGMENT

## Report
ACTION: ANSWER {"found": true or false, "secret": "the private fact you can prove and who it is about", "evidence_email_ids": ["e12","e37"]}
