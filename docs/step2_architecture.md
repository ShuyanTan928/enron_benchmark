# Step 2 Architecture — Secret Materialization

Step 2 takes an abstract topic and produces a `BenchmarkSecret`: a
single-paragraph description plus 2–3 `NecessaryFact`s that jointly imply
the secret (AND structure) while each remaining individually ambiguous.

Current state: **mean 20.0 / 22 success** on the standard 22-topic pool
(range 18–22 across 5 seeds; **15/22 secrets succeed under every seed**).
The result is deterministic within a fixed seed but seed-conditioned
across seeds — the secrets that flip all sit on the AND-redundancy
boundary. See [Seed stability](#seed-stability) for the full sweep.

## Pipeline

```
scripts/generate_secrets.py
    │
    ▼
src/secrets/generator.py : generate_secret_with_repair(topic, profiles, …)
    │
    ├─► _materialize_initial          (1 LLM call)
    │       SECRET_MATERIALIZATION_PROMPT
    │
    └─► main loop (max_repairs = 3)
            │
            ├─► normalize_facts        (0–3 LLM calls)
            │       rewrite + audit + synth passes
            │
            ├─► _run_validation        (V1–V9 + AND-redundancy)
            │
            ├─► do-no-harm rollback
            │       if post-normalize fails and pre-normalize passes,
            │       revert facts to the pre-normalize snapshot.
            │
            └─► repair_secret          (1 LLM call, if violations remain)
                    SECRET_REPAIR_PROMPT

        cycle-escape (after the loop, gated by detect_repair_cycle):
            repair_secret + final validate
            SECRET_CYCLE_ESCAPE_PROMPT
```

Output: `BenchmarkSecret` + `RepairReport` (status + trajectory + final
violations). The trajectory records every attempt, including
`normalize_rollback` events.

## Three generating prompts (same skeleton)

`SECRET_MATERIALIZATION_PROMPT`, `SECRET_REPAIR_PROMPT`, and
`SECRET_CYCLE_ESCAPE_PROMPT` share a forced-articulation structure. The
LLM is required to emit, in order: a STRUCTURE-PLAN block, a SELF-AUDIT
block, then the JSON.

### STRUCTURE-PLAN (reasoning first)

The plan is the LLM's pre-commitment. It must contain:

- `components` — independent semantic components of the secret, one per
  line. Each component is carriable by exactly one fact.
- `deceived_party_view_test` — `yes | no | n-a`. Perspective simulation:
  reading only the planned facts, would the deceived party form a false
  belief from information asymmetry alone? (Inspired by ToMATO and
  FANToM: information asymmetry induces false belief without a dedicated
  ignorance statement.)
- `ik_resolution_plan` — for each IK email, pick exactly one validator-
  V6 exit:
  - (A) `co_conspirator` — reason="co-conspirator", no KG fact.
  - (B) `unwitting_conduit` — reason="unwitting conduit", no KG fact.
  - (C) `sidelined_via_generic_role` — remove this IK entry AND replace
    their name in the description with a generic role label.
  - (D) `explicit_false_belief` — keep reason="deceived party", add a
    knowledge_gap fact. Valid only when `deceived_party_view_test = no`.
- `fact_count` — `2` if every IK is A/B/C, `3` if at least one is D.
- `fact_dimension_plan` — per-fact dimension (one of the allowed set).
- `atomic_proposition` — single-proposition paraphrase per fact:
  subject + active verb + object, no welded purpose / cover-story /
  causal / knowledge-gap clause. (FActScore, SAFE.) Weld patterns to
  reject: `X did Y as Z`, `X did Y to hide Z`, `X did Y, which Z didn't
  know`.

### FINAL CHECKS (recency position)

A short numbered list immediately before SELF-AUDIT, restating the hard
constraints LLMs most often drop after long planning text:

1. `fact_count` is exact. Never below 2, never above 3.
2. Number of components equals `fact_count` (if 4 components appear,
   merge two).
3. Each fact statement matches its `atomic_proposition` line.
4. Every IK reason field matches the picked exit (A→"co-conspirator",
   B→"unwitting conduit", C→IK removed, D→"deceived party").
5. If any IK picked C, the name must be replaced with a generic role
   label in the description.

### SELF-AUDIT (forced verdict, CoVe-style)

Every item answered `yes | no | n-a` in lowercase, no curly braces.
Items mirror the principles above, e.g. `structure_plan_emitted`,
`fact_count_matches_plan`, `ik_resolution_consistent_with_facts`,
`all_facts_atomic_no_weld`, `leave_one_out_pass`,
`every_fact_has_non_holder_observer`, `no_secret_vocabulary_leak`,
`no_weld_in_any_fact`.

If any item is `no`, the LLM revises silently and re-emits the audit
block until all items pass.

## Normalize sub-stage (`src/secrets/normalizer.py`)

Three passes per attempt, each optionally calling the LLM:

1. **Rewrite** (`FACT_ACTOR_REWRITE_PROMPT`) — when the fact's subject
   is non-human or passive, put a specific cast member in front while
   preserving every other token verbatim. Skip-default: do nothing if
   the fact already has a human subject in active voice.
2. **Audit** (`COMPONENT_COVERAGE_AUDIT_PROMPT`) — decompose the
   secret into clauses, classify each as observable_behavior /
   observable_artifact / observable_omission / motivation / mental_
   state, flag uncovered observable clauses. Motivation and
   mental_state are never flagged. A high-information guard prevents
   flagging clauses whose direct manifestation would collapse the AND.
3. **Synth** (`SYNTHESIZE_MISSING_FACT_PROMPT`) — for each flagged
   observable gap, generate one new fact. Self-check before emit:
   Q1 (carries the clause?), Q2 (reader can recover the secret from
   this fact alone? must be no), Q3 (verb echoes secret's verb? must
   be no). Refuse with `{}` if any check fails.

`normalize_facts` returns `(updated_secret, report)`. `report` includes
the rewrite log, audit clauses, synthesized facts, and any errors.

## Do-no-harm rollback

In each main-loop attempt:

```python
secret_pre_norm = secret.model_copy(deep=True)
secret, norm_report = normalize_facts(secret, …)
violations = _run_validation(secret, …)
if violations:
    pre_violations = _run_validation(secret_pre_norm, …)
    if not pre_violations:
        # normalize made AND worse; revert
        secret = secret_pre_norm
        violations = pre_violations
        trajectory.append({"action": "normalize_rollback", …})
```

This guarantees that `normalize_facts` never lowers AND quality. The
same check fires in the cycle-escape branch.

## Validator (`src/secrets/validator.py`)

The validator runs nine independent checks plus AND-redundancy on every
candidate fact set:

| Rule | Purpose |
|---|---|
| V1 | Actor-only-observable fact (no third-party witness possible) |
| V2 | knowledge_gap fact is a literal restatement of the secret |
| V3 | knowledge_gap with `is_actor_behavior=true` |
| V4 | description encodes multi-step intent |
| V5 | `minimum_clues` mismatches fact count |
| V6 | deceived party in IK but no knowledge_gap fact present |
| V7 | invalid dimension |
| V8 | fact_id sequence not F1..FN |
| V9 | description names cast not in IK |
| AND | leave-one-out: removing any one fact still uniquely implies |

V6 has three exits ((b)/(c) listed in the violation message); the
prompt's `ik_resolution_plan` surfaces these exits at plan time.

`_has_deceived_party_in_ik` exempts IK whose reason indicates co-
conspirator role OR contains the keyword `conduit` (used-as-proxy
role). Co-conspirator-only IK does not need a knowledge_gap fact.

## Outputs

- `secrets/step2.json` — list of `BenchmarkSecret` with `repair_report`
  attached. Status per secret is one of `success | partial | failed`.
- `secrets/step2_readable.txt` — human-friendly dump (via
  `scripts/dump_step2_readable.py`).

## Seed stability

The pipeline is deterministic within a fixed `--rng_seed` but its output
varies across seeds, because the generating prompts sample (non-greedy)
and the repair loop sometimes resolves a borderline fact set and
sometimes does not. To quantify this, the standard 22-topic pool was run
under five seeds on identical code and the same 4 GPUs (only the seed
varied). Reproduce with `scripts/seed_sweep.sh` + `scripts/summarize_seeds.py`.

### Per-seed success count

| seed | success | partial | failed |
|---|---|---|---|
| 42 | 22 | 0 | 0 |
| 123 | 21 | 1 | 0 |
| 7 | 20 | 0 | 2 |
| 31337 | 19 | 1 | 2 |
| 2024 | 18 | 0 | 4 |

**success = 18–22, mean 20.0** (n_seeds=5, n_secrets=22).

### Per-secret status across seeds

15/22 secrets succeed under every seed (the seed-invariant core). The
7 that vary, and the only secrets that ever fall short:

| secret | 7 | 42 | 123 | 2024 | 31337 | non-success |
|---|---|---|---|---|---|---|
| S03 | fail | ok | ok | ok | fail | 2/5 |
| S05 | ok | ok | ok | fail | fail | 2/5 |
| S16 | fail | ok | ok | fail | ok | 2/5 |
| S08 | ok | ok | partial | ok | ok | 1/5 |
| S17 | ok | ok | ok | fail | ok | 1/5 |
| S20 | ok | ok | ok | fail | ok | 1/5 |
| S21 | ok | ok | ok | ok | partial | 1/5 |

### Reading the result

- **Every non-success is `REDUNDANT_FACT`** (the AND-test leave-one-out
  judge). V1–V9, structure, and IK resolution are seed-invariant; the
  only unstable axis is whether one fact is redundant given the others.
- **No secret is ever permanently broken** — all 22 succeed under at
  least one seed. The 7 fragile ones sit near the AND-redundancy
  boundary and tip over depending on sampling.
- **Reporting:** a single "22/22" overstates precision. Report either
  the seed distribution (mean 20.0, range 18–22, 15/22 seed-invariant)
  or pin the seed and disclose it as seed-conditioned (seed 42 → 22/22).

## Design references

The prompt design draws on the following techniques. Each is named in
the prompt text where applied.

- **Tam et al. EMNLP 2024** — reasoning before answer: STRUCTURE-PLAN
  precedes JSON.
- **Chain-of-Verification (Dhuliawala, ACL 2024)** — SELF-AUDIT block
  forces explicit yes/no verdicts before final output.
- **ExploreToM (Meta AI 2024)** — abstract structure first, surface
  realization second; the two-stage pattern here is STRUCTURE-PLAN
  (structure) + JSON (realization).
- **FActScore (Min et al. EMNLP 2023) and SAFE (Wei et al. 2024)** —
  atomic decomposition: each fact paraphrasable as one atomic
  proposition; no welded clauses.
- **ToMATO (AAAI 2025) and FANToM (EMNLP 2023)** — information
  asymmetry induces false belief; `deceived_party_view_test` runs a
  mini perspective simulation.
- **Jaroslawicz et al. 2024 "How Many Instructions Can LLMs Follow at
  Once?"** — instruction-following rate decays with prompt length;
  FINAL CHECKS at recency position reactivates dropped constraints.

No case-specific keyword blacklists; every prompt rule is an abstract
principle or paper-validated mechanism.
