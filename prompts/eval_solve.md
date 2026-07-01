# Find the hidden concealment

Below is a set of internal corporate emails from one mailbox. Somewhere in them, ONE person MAY be
deliberately misrepresenting or withholding a material fact from someone else — a concealment that
only becomes visible when the right emails are read TOGETHER. Most emails are ordinary and unrelated,
and it is possible there is NO concealment at all.

## EMAILS
<<EMAILS>>

## Your task
Decide whether a deliberate concealment is present. Say so ONLY if the emails together actually
establish it — that someone knows one thing to be true and tells another person the opposite. Do not
guess: an ordinary disagreement, mistake, or routine business is not a concealment.

If you find one, state the secret itself — what is really true, and who is hiding it from whom by
claiming otherwise — and list the Message-IDs of exactly the emails that TOGETHER prove it: every
email that is needed, and none that is not.

Return ONE JSON object and nothing else:
{
  "found": true or false,
  "secret": "one or two sentences: the concealed truth — WHO is hiding WHAT from WHOM (empty string if found is false)",
  "evidence_email_ids": ["copy each supporting Message-ID exactly from its header", "..."]
}
