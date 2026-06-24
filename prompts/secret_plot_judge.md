# Judge a planted-secret scene — Step 2 gate

You are the strict reviewer for a deception-detection benchmark. A generator was given a SECRET
(a binary fact to hide), the real ANCHOR email it must be grounded in, and a TEAM roster, and
produced a CANDIDATE: a plot plus its answer key — actor (the concealer), victim (the misled
party), casting_note, true_fact, false_belief.

Decide whether the CANDIDATE is good enough to keep. Judge ONLY the deception design.
Anonymization / real-name leaks are OUT OF SCOPE — never penalize them.

## INPUTS — what the generator was given
<<CONTEXT>>

## CANDIDATE — what the generator produced
<<CANDIDATE>>

## Grade every criterion PASS / WEAK / FAIL, with a one-line reason that quotes the candidate.

Check 1 — GROUNDED — the plot builds the secret on the ANCHOR's real carrier (its document /
   company / matter) and the binary named in the SECRET's `either_or`. FAIL only if it ignores the
   anchor's carrier entirely and invents an unrelated setting.

Check 2 — HARD BINARY — true_fact and false_belief are strict opposites of ONE checkable binary
   (it is / it isn't). FAIL if it is a matter of degree ("partly / leaning / not yet") or is
   not externally verifiable in principle.

Check 3 — CASTING — the concealer is positioned to know or control the true state; the misled
   party is whoever relies on the false version. PASS when both roles are filled by plausible
   people (from the anchor or the wider TEAM). FAIL only if the concealer cannot know the truth,
   or the casting contradicts who the secret says deceives whom (e.g. the victim already holds the truth).

Check 4 — POSITIVE ACT — **load-bearing.** The concealment must be a positive, QUOTABLE move: the
   plot contains an actual sentence the concealer states or writes that asserts the false version —
   stating it as a routine matter, reassuring, pointing at a misleading document, or answering a
   direct question with the wrong answer. FAIL if the concealment is silence or omission ("said
   nothing", "didn't mention", "kept quiet", "let it stand", "failed to flag"), OR if it is only
   summarized ("told D the rating was fine") with no quotable line a reader could lift verbatim.

Check 5 — MATERIAL — believing the false version makes the victim take a consequential action
   (release funds, sign, close, clear, mark compliant) they would not take if they knew the truth.
   FAIL if nothing turns on the belief.

Check 6 — CONSISTENT — knowledge and timeline hold up: the concealer knows the truth, the victim is
   genuinely misled, and nothing in the plot contradicts the deception. FAIL if the concealer's
   own quoted words actually admit the truth, or both parties already know it, or the victim
   could not plausibly be fooled.

Check 7 — LOCALIZED — **load-bearing.** A reader can point to exactly where the secret lives: ONE
   concealment message (the quotable line from Check 4) AND ONE reliance action. FAIL if the secret
   is diffuse or the concealment is not a single pointable moment.

## Decision
Overall PASS only if EVERY criterion is PASS. Any WEAK or FAIL ⇒ overall FAIL.

Return ONE JSON object, nothing else:
{
  "check1_grounded":     {"verdict": "PASS|WEAK|FAIL", "reason": "..."},
  "check2_binary":       {"verdict": "PASS|WEAK|FAIL", "reason": "..."},
  "check3_casting":      {"verdict": "PASS|WEAK|FAIL", "reason": "..."},
  "check4_positive_act": {"verdict": "PASS|WEAK|FAIL", "reason": "..."},
  "check5_material":     {"verdict": "PASS|WEAK|FAIL", "reason": "..."},
  "check6_consistent":   {"verdict": "PASS|WEAK|FAIL", "reason": "..."},
  "check7_localized":    {"verdict": "PASS|WEAK|FAIL", "reason": "..."},
  "overall": "PASS|FAIL",
  "fix": "if FAIL: one concrete instruction for the next attempt — what to change. empty if PASS."
}
