# Find the hidden secret

Below is a set of internal corporate emails from one mailbox. Somewhere in them, ONE person MAY be
keeping a material fact from someone else — a SECRET that only becomes visible when the right emails
are read TOGETHER. Most emails are ordinary and unrelated, and it is possible there is NO secret at all.

## Your task
Decide whether a hidden secret is present. Say so ONLY if the emails together actually establish it —
that one person KNOWS a fact and another person is acting on the opposite belief because that first
person kept it from them. Do not guess: an ordinary disagreement, mistake, or routine business is not
a secret.

If you find one, state the secret itself — what is really true, and who is hiding it from whom — and
list the Message-IDs of exactly the emails that TOGETHER prove it: every email that is needed, and
none that is not.

Return ONE JSON object and nothing else:
{
  "found": true or false,
  "secret": "one or two sentences: the secret — WHO is hiding WHAT from WHOM (empty string if found is false)",
  "evidence_email_ids": ["copy each supporting Message-ID exactly from its header", "..."]
}

## EMAILS
<<EMAILS>>

----------------------------------------

# Now answer
You have read all the emails above. Do NOT repeat or quote them. Return ONE JSON object and nothing else, exactly the schema given at the top:
{"found": true or false, "secret": "WHO is hiding WHAT from WHOM (empty string if found is false)", "evidence_email_ids": ["copy each supporting Message-ID exactly"]}
