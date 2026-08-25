# Write each clue's emails from its scene

You're given each clue's scene (`plot`) and the atom(s) it carries. Turn each into a real work email in the
sender's voice — one message, or a short reply chain on one subject (three for a3). 

Firm people are Person A…J (written out in full); outside parties keep real names (may
have none); our company is "[firm]". Every email has to sit plausibly in a real work mailbox.

## The matter
actor (conceals): <<ACTOR>>   victim (misled): <<VICTIM>>

## The team — use only these
<<TEAM>>

## Voice — write each sender in their own hand
Each person's style, then two emails they wrote. Match a sender's greeting, length, punctuation and sign-off
to their samples; borrow the voice only, none of the names, numbers or matters.
<<VOICES>>

## The clues — one thread per clue
<<PLOTS>>

## Rules
1. Carry each fact through the email itself — e.g. its date, the header, the subject, a forwarded or
   pasted record, or the body. Keep the plot's shared reference exactly (e.g. the file, thread, or matter it links the clues by).
2. The a3 clue: <<A3_ACT>> If the plot has the victim rely, write one thread — the actor's message, then
   the victim's short reply that takes it at face value and acts. The truth never surfaces; the reply
   doesn't echo the details or the actor's own words.
3. Each clue is its own thread on its own subject — never a reply to, or a quote of, another clue.
4. Read like real <<ERA>> work mail — not a bare line, not padded either. The prose stays terse and a
   little sloppy (lowercase, fragments, an occasional "&"/"w/"/typo — not every line). Most messages just
   sign off with the sender's name; only now and then does one close on a full block (name, [firm] Corp,
   address, phone). The extra length comes mainly from a forward or reply carrying its quoted material
   below (Rule 5), not from more prose.
5. Render a forward or reply the way Enron mail does: a short lead line, then a separator
   ("-----Original Message-----", or "---- Forwarded by <Name> on <date> ----") above the quoted
   To:/cc:/Subject: lines and the quoted text beneath. That quoted text carries ONLY this clue's own
   atom — never another clue's; a forward that just shares a neutral handle quotes the cover, not the truth.

<<FEEDBACK>>
Dates fall around <<ERA>>, ordered so chains read right. Return ONE JSON object, nothing else:
{"clues":[{"i":1,"carries":["a1","a2"],"plot":"...","messages":[{"from":"Person ?","to":["Person ?"],"cc":[],"date":"YYYY-MM-DD","subject":"...","body":"..."}]}]}
