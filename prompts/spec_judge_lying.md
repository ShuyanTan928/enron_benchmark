# Judge the ATOMS of a concealment — type: LYING

You are the strict reviewer for a deception-detection benchmark. This gate is type-specific: it
checks whether the SECRET, as captured in the CANDIDATE atoms, is a valid **LYING** concealment —
i.e. whether it decomposes into three clean lying atoms a1 (truth) / a2 (actor knows) / a3 (false
statement) that a later step can turn into clue emails. (Other secret_types load their own judge.)

Judge ONLY the deception design and the atom decomposition. How each atom is made OBSERVABLE (a date,
a To line, a pasted record) and how many clues it becomes (n) are decided DOWNSTREAM — do NOT judge
those here, and do NOT require an atom to already name its observable form. Anonymization / real-name
leaks are OUT OF SCOPE — never penalize them.

## INPUTS — what the generator was given
<<CONTEXT>>

## CANDIDATE ATOMS
<<CANDIDATE>>

Grade every check PASS / WEAK / FAIL, each with a one-line reason that quotes the candidate. Overall
PASS only if EVERY check is PASS; any WEAK or FAIL ⇒ overall FAIL.

The TOPIC (its binary, its grounding on the anchor, its materiality) was ALREADY gated upstream — do
NOT re-judge whether it is a good lying topic. Judge only whether the atoms DECOMPOSE it correctly.

## PART A — faithful decomposition

check_faithful — the atoms decompose the SAME secret the CONTEXT gives: answer_key.true_fact /
   false_belief restate the topic's binary (not a drifted or different concealment), a1 is the true
   side, a3 asserts the false side. FAIL only if it has wandered to a different secret than the topic.

## PART B — the three LYING atoms

### a1 — the truth F
check_a1_clean — `a1.fact` is the single true fact F with its real specifics, and ONLY that. FAIL if
   it is the bare conclusion word instead of the fact ("the trade was unauthorized" / "the guaranty
   is expired" rather than the directive / dated record that fact rests on), OR if it is padded with
   the deal that was done or the victim's action (that belongs in reliance_rule, not a1). a1 MAY
   quote a record's own wording even when that wording is a state-change verb (a letter that SAYS
   "the guaranty is revoked" is a fact, not a gloss).

### a2 — the actor knows F
check_a2_knows — `a2.fact` states the actor's knowing relation to F ("Person X knows <F>") and
   nothing more. A plain "knows" is CORRECT here — do NOT require an observable handle (received /
   signed / custodian); that is chosen downstream. FAIL only if a2 is about someone other than the
   actor, is not about F, or smuggles in the false line or the deal.

### a3 — the actor asserts ¬F to the victim
check_a3_false_line — **load-bearing.** a3 is an actual quotable sentence the actor asserts to the
   victim that is FALSE given a1 with NO honest reading. FAIL if it is silence / omission ("said
   nothing", "didn't mention", "failed to flag"), a mere summary with no quotable line, a hedge /
   opinion, or if it also states the truth (which would self-leak). (Silence/omission and
   true-but-misleading are OTHER secret_types, not lying.)

## PART C — the atoms hold together

check_casting — the actor is positioned to hold/know the truth (supports a2); the victim is whoever
   relies on the false version; `reliance_rule` is a plain victim action on the false belief with no
   challenge and no rebuttal surfacing the truth. FAIL if the actor cannot know the truth, the victim
   already holds it, or the reliance is written as an explicit "relying on the false assurance" tell.

check_decomposable — a1 and a3 are separable: the truth and the false line are cleanly opposite and
   can sit in different clues, and a3 does not restate the truth. FAIL only if a1 and a3 cannot be
   pulled apart (the false line and the truth are inseparable). How many clues the secret carries (n)
   and how a1 might split are decided downstream — NOT this judge's concern.

## Output — ONE JSON object, nothing else
{
  "check_faithful":      {"verdict": "PASS|WEAK|FAIL", "reason": "..."},
  "check_a1_clean":      {"verdict": "PASS|WEAK|FAIL", "reason": "..."},
  "check_a2_knows":      {"verdict": "PASS|WEAK|FAIL", "reason": "..."},
  "check_a3_false_line": {"verdict": "PASS|WEAK|FAIL", "reason": "..."},
  "check_casting":       {"verdict": "PASS|WEAK|FAIL", "reason": "..."},
  "check_decomposable":  {"verdict": "PASS|WEAK|FAIL", "reason": "..."},
  "overall": "PASS|FAIL",
  "fix": "if FAIL: one concrete instruction for the next attempt — what to change. empty if PASS."
}
