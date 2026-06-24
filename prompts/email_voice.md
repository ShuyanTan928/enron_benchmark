# Step 3 — voice pass: re-render each email in its sender's voice

Rewrite the BODY of each email below in its sender's own voice — change only word choice and
phrasing habits. Keep every fact, add nothing, drop nothing. Do NOT add a signature block, contact
details, a disclaimer, or any sentence that is not already carrying one of the facts below. Keep
From / To / Cc / Date / Subject exactly as given.

## SENDER VOICE NOTES
<<VOICES>>

## EMAILS — rewrite each Body in the sender's voice
<<EMAILS>>

## FACTS THAT MUST ALL SURVIVE (do not drop, alter, or add to — introduce NO new fact beyond these)
<<ATOMS>>

Do not name the secret; do not use words like hide / conceal / cover / breach as a label.
Return ONE JSON object, nothing else:
{"messages": [{"from": "...", "to": ["..."], "cc": [], "date": "...", "subject": "...", "body": "<rewritten body>"}]}
