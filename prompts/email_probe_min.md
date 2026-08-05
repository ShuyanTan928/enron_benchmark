# Find the hidden secret

Below is a set of internal corporate emails from one mailbox. Somewhere in them, one person may be
keeping a secret — by saying something false, by leaving it out, or by saying something technically true
that leaves the wrong impression. It is possible there is no secret at all.

## Your task
Decide whether a hidden secret is present. Say so only if the emails together actually establish it.

Return ONE JSON object and nothing else. If "found" is false, ALL other fields MUST be the empty string "":
{
  "found": true or false,
  "actor": "the person hiding it",
  "victim": "the person kept in the dark",
  "true_fact": "what is actually true",
  "false_belief": "what the victim is led to believe instead",
  "knew": "the email/record that shows the actor knew the true fact — where they were told it, received it, or hold it"
}

## EMAILS
<<EMAILS>>
