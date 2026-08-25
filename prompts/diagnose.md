# Diagnose the clue set

The blind reader either leaked the secret from a subset, or failed to recover it from all clues together.
Both come from ONE clue being mis-set — it said too much or too little. Name that clue, state the
two-sided job it must hold, and give ONE change that lands in the MIDDLE — never a swing into the
opposite failure. The ATOMS ARE FIXED — every fix redesigns the SCENES: which record carries each fact,
who receives it, the handles, the dates.

## The secret (answer key)
actor: <<ACTOR>>   victim: <<VICTIM>>
secret: <<SECRET>>

## The clue set
<<CLUES>>

## What the blind reader found
all clues together: <<JOINT>>
subsets:            <<LEAKAGE>>
thread structure:   <<STRUCTURE>>
already tried — don't repeat, and don't just reverse into the opposite failure: <<HISTORY>>

<<SET_MODEL>>

## Each clue is a dial with two ends — a fix has to hold BOTH
- a1 (truth): says the truth clearly enough that a1+a2 recover it — but not so fully that {a1,a3} alone
  completes the secret. too much = it names the subject AND the whole outcome in one clue; too little =
  only a filename or a vague "there's a flag", no truth in the body.
- a2 (knew): shows the actor was on the SAME record/thread as a1 (so they'd have seen it) — but never
  restates its content, and its handle/filename must not spell the outcome. too much = the reply or the
  filename states the fact; too little = a bare receipt on no shared handle, so it proves nothing.
- a3 (act): the actor's move to the victim — a false line (lying by commission), or a TRUE line on the SAME matter
  that confirms its visible side is fine (paltering). too much = it names or points at the hidden record;
  too little (paltering) = it drifted to a DIFFERENT matter, so it misleads no one and the set can't
  recover — put it back on the matter the victim is deciding, pointing to something genuinely in good order.
A leak = that clue said too much; a non-recovery = it said too little. If a past attempt emptied the clue
and broke recovery, do NOT re-fill it with content — prove the point the other way (shared handle, a
receipt on the same thread, a standing record).

## Some fixes need TWO clues to move together — name both
A single clue can't always land it, because the fix couples clues:
- a1 and a2 must share ONE neutral handle: if a1's handle spells the outcome, making a2 neutral just
  breaks the link — instead re-label a1's record to a neutral handle X AND point a2's receipt at that same X.
- when the fact is about the actor themselves: de-identify the subject on a1 (an applicant id, a case
  ref) AND have a2 carry the identity link (the actor is that applicant / holds that case).
When the change spans clues, list ALL of them in `clues` and describe how they line up.

## Output — ONE JSON object, nothing else
{
  "recovered": true | false,
  "modes": [{"mode": "SUBSET_LEAK | FULL_SET_DOESNT_RECOVER", "where": "clue N / one line why"}],
  "fix": {
    "clues": [N],
    "must_keep": "the side each named clue must NOT lose",
    "overshot": "the side it crossed this time (or would cross if you just reverse the last attempt)",
    "change": "one concrete change that satisfies BOTH — if two clues must move together (a shared handle, a matching date, an identity link), say how they line up, e.g. a1 and a2 share ONE neutral handle X: a1's record is labeled X, a2's receipt refers to the same X"
  }
}
