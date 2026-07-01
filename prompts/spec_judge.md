# Judge a concealment SPEC — the generation gate

You are the strict reviewer for a deception-detection benchmark. A generator was given a SECRET (a
binary fact to hide), the real ANCHOR email, and a TEAM, and produced a CANDIDATE SPEC: actor,
victim, answer_key, and the three atoms a1 (truth) / a2 (actor knows) / a3 (false statement), with
a1 split into operands. Decide whether the SPEC is good enough to build clue emails from.

Judge ONLY the deception design and the atom decomposition. Anonymization / real-name leaks are OUT
OF SCOPE — never penalize them.

## INPUTS — what the generator was given
<<CONTEXT>>

## CANDIDATE SPEC
<<CANDIDATE>>

## Grade every criterion PASS / WEAK / FAIL, each with a one-line reason that quotes the candidate.

Check 1 — GROUNDED — the spec builds on the ANCHOR's real carrier (its document / matter /
   counterparty) and the binary named in the SECRET's `either_or`. FAIL only if it ignores the
   anchor entirely and invents an unrelated setting.

Check 2 — HARD BINARY — answer_key.true_fact and false_belief are strict opposites of ONE checkable
   binary (it is / it isn't). FAIL if it is a matter of degree ("partly / leaning / not yet") or is
   not externally verifiable in principle.

Check 3 — CASTING — the actor is positioned to hold or control the truth; the victim is whoever
   relies on the false version. FAIL only if the actor cannot know the truth, or the casting
   contradicts who deceives whom (e.g. the victim already holds the truth).

Check 4 — a1 IS OBSERVABLE, NOT A CONCLUSION — `a1.fact` and every operand state observable facts
   (a dated record, an absence on file, a figure), NOT the spec's own conclusion gloss (lapsed / void
   / breached / missed / expired). An operand MAY quote a record's own wording even when that wording
   is a state-change verb — a letter that SAYS "the guaranty is revoked" is an observable record-quote,
   not a gloss. FAIL only when the spec NARRATES the conclusion as its own (not quoting a record).

Check 5 — OPERANDS ARE INDEPENDENT, INNOCUOUS, AND HIDEABLE — **load-bearing.** This is the core of
   the decomposition. For a MULTI-operand a1, each operand must be (a) HIDEABLE — a specific fact that
   can be kept out of a clue; NEVER the ambient current/today's date, a message's own send-date, or
   anything on every email header (those cannot be hidden, so they do not split the secret — they
   leak the other operand); (b) innocuous ON ITS OWN — a reader seeing only it has no reason to
   suspect a concealment; and (c) independent — not derivable from another. The contradiction must
   arise ONLY when all operands are read together. FAIL if: a comparison/judgment was left as ONE
   operand instead of split into REFERENCE and ACTUAL; OR an operand is the current/today's date / a
   send-date / a header-visible fact; OR an operand already reveals the bad fact alone; OR one is
   derivable from another. For an EXPIRY the operands must be (the dated instrument + its term) and
   (NO renewal/successor on file) — NOT (end-date)+(today). EXCEPTION: a SINGLE-declaration a1 (one
   record that states the fact outright, e.g. a letter saying the guaranty is revoked) is PASS and is
   NOT subject to the innocuous-alone test — it has nothing to compare, caps the secret at n=2, and
   the *concealment* still needs a3 in a separate clue.

Check 6 — a2 KNOWLEDGE AND ITS FLAG — a2 is an OBSERVABLE handle on the truth in the actor's hands
   (authored / signed / received / holds / custodian), not "X knew". AND `obvious_from_casting` is
   correct: true when the actor is by-role the custodian (a2 then rides, `core: false`); false only
   when the actor is NOT the natural custodian and a2 carries real information (`core: true`). FAIL
   if a2 is a bare mental-state claim, or the flag is wrong (e.g. an obvious custodian marked
   `core: true`, or a non-custodian's knowledge asserted with no observable basis).

Check 7 — a3 IS A POSITIVE FALSE LINE — **load-bearing.** a3 is an actual quotable sentence the
   actor asserts to the victim that is FALSE given a1 with NO honest reading. FAIL if it is silence
   / omission ("said nothing", "didn't mention", "failed to flag"), a mere summary with no quotable
   line, a hedge/opinion, or if it also states the truth (which would self-leak).

Check 8 — n_ceiling AND RELIANCE — n_ceiling equals (number of a1 operands) + 1, plus 1 only if
   a2.obvious_from_casting is false; and `reliance_rule` describes a plain victim action on the
   false belief with no challenge / no rebuttal surfacing the truth. FAIL if n_ceiling is
   miscomputed, or the reliance is written as an explicit "relying on the false assurance" tell, or
   the rule lets the victim challenge / the truth surface in the threads.

## Decision
Overall PASS only if EVERY criterion is PASS. Any WEAK or FAIL ⇒ overall FAIL.

Return ONE JSON object, nothing else:
{
  "check1_grounded":      {"verdict": "PASS|WEAK|FAIL", "reason": "..."},
  "check2_binary":        {"verdict": "PASS|WEAK|FAIL", "reason": "..."},
  "check3_casting":       {"verdict": "PASS|WEAK|FAIL", "reason": "..."},
  "check4_a1_observable": {"verdict": "PASS|WEAK|FAIL", "reason": "..."},
  "check5_operands":      {"verdict": "PASS|WEAK|FAIL", "reason": "..."},
  "check6_a2_knew":       {"verdict": "PASS|WEAK|FAIL", "reason": "..."},
  "check7_a3_positive":   {"verdict": "PASS|WEAK|FAIL", "reason": "..."},
  "check8_ceiling":       {"verdict": "PASS|WEAK|FAIL", "reason": "..."},
  "overall": "PASS|FAIL",
  "fix": "if FAIL: one concrete instruction for the next attempt — what to change. empty if PASS."
}
