# Blind read — is anyone deliberately misleading anyone?

You are reading a few ordinary work emails pulled from a corporate mailbox. Read them neutrally. Most
mail is innocent, and a mismatch between two documents is usually an ordinary gap, a later update, or
two unrelated facts — NOT deception. Do not strain to find a hidden secret; report only what the
emails actually let you establish.

## EMAILS
<<EMAILS>>

## Decide
Deliberate misleading needs ONE person who, KNOWING the true state of affairs, tells someone else the
opposite. To answer yes you must be able to point, from these emails ALONE, to ALL THREE:
  (a) the true state of affairs;
  (b) that the SAME person who made the claim KNEW it — they wrote it, received it, hold it, or are
      named on the record that carries it; NOT merely that the truth exists somewhere in the mail;
  (c) that this person told someone else the opposite.
A true state plus a contradicting claim is NOT enough on its own: if you cannot show that the person
who made the claim actually knew the true state, answer no — it may be an honest mistake or two
unrelated facts, which is not deliberate misleading. Knowledge you cannot point to is not knowledge.

Return ONE JSON object — nothing else:
{
  "hidden": true | false,
  "who": "the person doing the misleading, or \"\"",
  "whom": "the person being misled, or \"\"",
  "about": "the fact being misrepresented, or \"\"",
  "knew_how": "the email evidence that this same person KNEW the true state (wrote / received / holds / named on it), or \"\""
}
Set "hidden": false whenever "knew_how" would be empty.
