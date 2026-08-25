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
