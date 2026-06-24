# Blind read — is anything being hidden?

You are reading a few ordinary work emails pulled from a corporate mailbox. Read them carefully,
as an investigator who starts out suspecting nothing.

## EMAILS
<<EMAILS>>

## Decide
Do these emails, ON THEIR OWN, let you establish that someone is deliberately misrepresenting or
withholding a material fact from someone else? Say yes only if you could actually point to it
here — the real state of affairs and the contradicting claim both visible — not a vague
possibility or a hunch.

Return ONE JSON object — nothing else:
{
  "hidden": true | false,
  "who": "the person doing the misleading, or \"\"",
  "whom": "the person being misled, or \"\"",
  "about": "the fact being misrepresented, or \"\""
}
