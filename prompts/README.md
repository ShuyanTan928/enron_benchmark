# Prompts

Every prompt that shapes the benchmark lives here — the `.md` templates below and the structured
fillings under `fills/`. Nothing prompt-affecting is hidden in Python anymore; the code only loads these
files and splices values into their `<<PLACEHOLDER>>` slots.

## Generation pipeline (one topic → its clue emails)

| # | step | template | fillings it splices in |
|---|------|----------|------------------------|
| 1 | **topic** — invent one abstract one-line secret | `topic_generate.md` | `fills/registers.json` (per-register setting / clause / matter_hint / example) |
| 1b | **grounding** (work only) — find a real anchor email | `grounding/hyde.md`, `grounding/fit_judge.md` | — |
| 2 | **atomize** — place the secret on a1/a2/a3, cast the people, write the answer-key secret | `atomize.md` | `fills/examples.json` → `atomize`; `fills/mechanisms.json` (the a3 act, as `<<A3_ACT>>`) |
| 3 | **plot** — one observable scene per clue | `clue_plot.md` | `fills/examples.json` → `plot`; `fills/separation.json` → `separation` (the AND-gate model per n) |
| 4 | **email** — write each scene as a real email in the sender's voice | `clue_email.md` | voice bank (`benchmark_pool/style_bank.json`) |
| 5 | **AND-check** — a blind prober tries to recover the secret; a judge scores the match; a diagnoser fixes a failed set | `probe.md`, `match.md`, `diagnose.md` | `fills/separation.json` → `set_model` (diagnose's model-of-the-set per n) |

## Evaluation (a tester model hunts the planted secret)

| prompt | role |
|--------|------|
| `agent.md` | the find-secrets ReAct agent's system prompt (native runner + Inspect port) |
| `agent_scan.md` | segment-scan variant of the agent prompt |
| `match.md` | the recovery judge — **the same prompt used at generation's AND-check**, so the gate judges what eval judges |

## The two testers speak the same shape

Both the generation prober (`probe.md`) and the eval agent (`agent.md`) output a single `secret`
sentence — the concealed fact, who concealed it, and who was misled. The answer key stores that same
one sentence (`answer.secret`). `match.md` compares the two sentences, checking all three parts.

## `fills/` — structured fillings (JSON)

| file | what it holds | loaded by |
|------|---------------|-----------|
| `registers.json` | per-register `setting` / `clause` / `matter_hint` / `example` for topic generation | `src/grounding/prompts.py` |
| `mechanisms.json` | the three concealment mechanisms (commission / omission / paltering): the a3 act definition (`render`), the atom role, and the gate checks | `src/grounding/prompts.py` (`render` → atomize/plot/email; checks → the topic gate) |
| `examples.json` | `atomize` = worked a1/a2/a3 per cell; `plot` = worked scene per (n, cell) | `scripts/atomize_build.py` |
| `separation.json` | `separation` = the AND-gate casting model per n (2/3/4) for the plot prompt; `set_model` = the model-of-the-set per n (3/4) for the diagnose prompt | `scripts/atomize_build.py`, `scripts/email_generate.py` |

## Placeholder conventions

- `<<SETTING>>` — the generic energy-firm setting (never names the real company).
- `<<ACTOR>>` / `<<VICTIM>>` — the cast, as `Person X — the concealer` / `Person Y — the misled party`.
- `<<SECRET>>` — the answer-key secret sentence (match / diagnose).
- `<<FINDING>>` — a tester's recovered secret sentence (match).
- `<<A3_ACT>>` — the concealing-act definition for the item's mechanism (from `mechanisms.json`).
- `<<EXAMPLE>>` / `<<EXAMPLE_PLOT>>` — the worked example for this cell (from `examples.json`).
- `<<SEPARATION>>` / `<<SET_MODEL>>` — the AND-gate model for this n (from `separation.json`).
- `<<ERA>>` — the item's date window (2000–2001).

## Not on the active path (kept for legacy tooling, not used by streaming generation)

`agent_recover_judge.md` (superseded by `match.md`), `eval_judge.md`, `eval_solve.md`, `noise_prober.md`,
`topic_judge_concealment.md`; and in `src/grounding/prompts.py`, the `TOPIC_GEN_PROMPT` / `SPECIALIZE_PROMPT`
/ `CHECK_PROMPT` constants (the older grounded-with-specialize path).
