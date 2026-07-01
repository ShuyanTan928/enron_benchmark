# Invent a concealment topic from a real anchor — type: LYING

You design items for a deception-detection benchmark. Given ONE real Enron email (the ANCHOR), invent
a plausible **lying** concealment that could sit on that email's real matter. You are NOT writing the
scene or the emails yet — only the SECRET: the one binary fact that gets hidden.

People are anonymous labels (Person A…J). Never name a real company; the firm is "[firm]".
Counterparties named in the anchor are real and stay.

## ANCHOR — the real email and its matter
<<ANCHOR>>

## TEAM — the people who could be involved
<<RELATIONSHIPS>>

## What a LYING topic must be
A lie is: someone, KNOWING a fact, asserts the opposite to a person who relies on it. So the secret
you invent must have all of:

1. **A BINARY fact about the anchor's matter** — a state that simply is or isn't, checkable in
   principle: an authorization is valid / lapsed; a limit is within / breached; an approval exists /
   never obtained; a clause is present / absent; a deadline is open / already passed; a guaranty is
   in force / withdrawn. NOT a matter of degree, opinion, or prediction.

2. **A concealer who would CONTROL or HOLD that fact** — the person whose file / record / job covers
   it (a coordinator, counsel, credit officer), so they could know the true side.

3. **A victim who RELIES on the fact** — someone who, believing the good side, takes a consequential
   action (proceeds, books, signs, clears, marks compliant) they would not take if they knew the bad
   side. This is what makes it material.

4. **ASSERTABLE** — there must be a clean POSITIVE sentence the concealer could say asserting the
   good (false) side as routine fact ("documentation is in order — approved to trade"). If the only
   way to hide it is silence, it is NOT a lying topic (that is omission — a different type).

Build the secret on the anchor's REAL matter (its deal, document, counterparty, regulatory subject).
Do not invent an unrelated scenario. Reuse the anchor's specifics where natural.

## Output — ONE JSON object, nothing else
{
  "topic_id": "<<TID>>",
  "secret_type": "lying",
  "name": "a 3-6 word handle for the secret",
  "secret": "one paragraph: a [role] conceals from a [role] that [the bad side of the binary], allowing [the reliant action] to continue as though [the good side], because disclosing it would [the cost]. Built on the anchor's matter.",
  "either_or": "SIDE A: <the good side the victim believes> vs SIDE B: <the bad side that is true>"
}
