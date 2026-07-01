# Enron Benchmark

A two-stage pipeline that builds a **distributed-clue deception-detection benchmark** from the Enron
email corpus. Each item hides a deliberate concealment across several individually-innocuous emails:
no single email gives the secret away, but read together they reveal *who concealed what from whom*.
The benchmark measures whether an LLM can recover that hidden concealment from the joined evidence.

---

## Project Overview

The pipeline runs in two named stages. **Spec Generation** decides *what* each secret is, grounds it
on the real corpus, and decomposes it into the indivisible facts a reader must reconstruct; **Email
Generation** distributes those facts over N clue emails and buries them in real Enron noise.
Generation and validation are always split across vendors (generate = Sonnet, judge / blind-probe =
GPT-5.4 + others) so the model that writes a secret never grades it.

> **`lying` is only the first secret-type — not the whole space of concealment.** The pipeline is
> type-pluggable (`--secret-type`): a *lying* secret (the actor knows `F` and asserts `¬F`) is one
> mechanism, but people hide things in many ways, and each would get its own atom decomposition + gates:
> - **omission** — withholding a material fact without ever asserting a falsehood (not disclosing a
>   conflict of interest, an off-book liability);
> - **paltering / half-truth** — technically-true statements that build a false impression (reporting
>   only the favorable slice of the numbers);
> - **falsified / backdated records** — the document itself is the lie;
> - **collusion** — two or more actors coordinating to keep something hidden (a multi-actor secret);
> - **insider tipping / self-dealing** — acting on material non-public knowledge.
>
> Every secret in this repo is currently a `lying` secret; the others are on the roadmap.

A **lying** concealment is exactly three atoms — the actor, knowing a fact, asserts the opposite to
the victim. The victim's reaction and the motive are *rules*, not atoms (a grounded workplace secret
is material, so a knowing false statement is deliberate, by construction):

| atom | what it is | drives the clue-count? |
|------|-----------|------------------------|
| **a1** `true_state` | the observable truth `F`; a *judgment* (expired / over-limit) splits into independent operands `a1.1, a1.2 …`, each innocuous alone | **yes** — operands + a3 set `n_ceiling` |
| **a2** `knew` | an observable handle on `F` in the actor's hands (authored / received / holds) | rides along; **own clue only** when knowledge is *not* obvious from the actor's role |
| **a3** `false_statement` | the actor's positive, quotable assertion of `¬F` to the victim — no honest reading | **yes** — always its own clue (never shares with a1) |

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  STAGE 1 — SPEC GENERATION                          what the secret is + where ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  [1] Topic  secret-FIRST (scripts/ground_topics.py --secret-type lying): seed an ║
║  (gen→gate) abstract lying secret → HyDE → BM25 retrieve a real anchor from the   ║
║             corpus → specialize onto it. A type gate (topic_judge_lying:          ║
║             grounded · binary · concealer-controls · material · assertable) keeps ║
║             only secrets SUITED to lying.   ⇒ benchmark_pool/topics_lying.json    ║
║                                                                                 ║
║  [2] Spec   decompose each topic into the canonical SPEC: a1 (truth, split into  ║
║  (gen⇄judge) the indivisible observations it rests on) · a2 (actor knows) · a3   ║
║             (false statement) + answer_key + reliance_rule. The conclusion lives  ║
║             ONLY in answer_key; how far a1 splits is the model's call, not a knob.║
║             spec_judge_lying gates faithful-decomposition + a1/a2/a3 + AND-split. ║
║                                                                                 ║
║   gen = Sonnet · judge/gate = GPT-5.4   (prompts: topic_judge_lying, spec_*_lying)║
║   ⇒ deliverable:  benchmark_pool/specs_lying.jsonl   (per-topic SPEC)           ║
╚══════════════════════════════════════════════════════════════════════════════╝
                                     │
                                     ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║  STAGE 2 — EMAIL GENERATION                         the actual benchmark emails ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Plan       deterministic clue→atom assignment for the chosen n (CPU, no API):  ║
║  (template) a3 is ALWAYS its own clue; the other n-1 hold the independent truth ║
║             operands (a1.1, a1.2, …; + a2 if its knowledge is its own           ║
║             observable). n=2: {ops+a2}{a3}.  n=3: {a1.1}{a1.2}{a3}.             ║
║             n > n_ceiling ⇒ this secret can't carry n — split the truth into    ║
║             more independent operands to raise it. a1 and a3 NEVER share a clue. ║
║                                                                                 ║
║  Render     ONE call: write the n clue emails from the SPEC + assignment. Each   ║
║  (gen⇄       clue carries ONLY its assigned atom(s) → leaks prevented by         ║
║   diagnose) construction. AND-check (subset probe) confirms; diagnose + iterate. ║
║                                                                                 ║
║   gen = Sonnet · probe/diagnose = GPT-5.4 ∨ Gemini-3.1 (joint OK if ANY recovers)║
║   ⇒ deliverable:  benchmark_pool/emails_lying_n<n>.jsonl                         ║
║                                                                                 ║
║  Assemble   bind Person A–J → real Enron identities, embed the clue emails in   ║
║  (CPU)      real Enron noise, interleave by date.                               ║
║   ⇒ deliverable:  data/benchmark/<TID>_haystack.jsonl  +  <TID>_answer.json     ║
╚══════════════════════════════════════════════════════════════════════════════╝
                                     │
                                     ▼
  STAGE 3 — EVALUATION:  tester fills {found, secret, evidence_ids} → fixed Sonnet judge →
                         FINAL = (found×secret_match) × (recall×precision) → figures A/B/C
```

Each stage feeds the next: Spec Generation emits one SPEC per secret (the indivisible atoms + answer
key); Email Generation plans a leak-free clue→atom distribution for the chosen `n`, renders the clue
emails in one call, validates that no clue or subset leaks alone, and plants them in the corpus to
form one benchmark sample per secret. The `n` a secret can carry is bounded by `n_ceiling` —
splitting the truth into more independent operands (or a non-obvious `a2`) is the only way to raise it.
The canonical living spec is [`docs/pipeline_v2.md`](docs/pipeline_v2.md).

---

## Stage 3 — Evaluation & Scoring Rubric

A tester model reads one assembled haystack (the clue emails hidden in `noise` real Enron distractor
emails) and fills **one form** — nothing leading, no hint that a concealment exists or how many clues
there are:

```jsonc
{ "found": true|false,             // is there a deliberate concealment at all?
  "secret": "...",                 // WHO hides WHAT from WHOM, in the tester's own words
  "evidence_email_ids": [ ... ] }  // the Message-IDs that TOGETHER prove it
```

Scoring is a **multiplicative gate** — every stage must clear or the score collapses, so a blind
"there is a secret" earns nothing:

```
secret_score   = found ∈{0,1}  ×  secret_match ∈{0,1}      # a FIXED Sonnet judge decides the match
evidence_score = recall × precision ∈ [0,1]
     recall    = |cited ∩ true clues| / |true clues|        # did it cite every clue?
     precision = |cited that are clue emails| / |cited|      # and only clue emails?
FINAL          = secret_score × evidence_score  ∈ [0,1]
```

- **`found` + judge kill blind guessing.** `secret_match` is decided by a fixed external judge
  (Sonnet 4.6) comparing the tester's stated secret to the answer key on all four of *concealed fact ·
  direction (true vs. claimed) · actor · victim*. Getting any wrong → 0.
- **`evidence` enforces the AND property at scoring time.** Recovering the secret from a proper subset
  still loses points for the clues it never cited, and over-citing noise costs precision.
- **One ruler.** The judge is the same model for every tester (cross-vendor from most, never
  self-judging), so scores are comparable across models.

| FINAL | meaning |
|---|---|
| 0 | wrong secret — or right secret with empty/garbage evidence → no recovery |
| 0 – 0.3 | secret right but poorly grounded → likely a lucky guess |
| 0.3 – 0.7 | secret right, partial evidence → partial recovery |
| 0.7 – 1 | secret right, most/all clues cited → solid recovery |
| 1 | perfect: right secret + the exact clue set (none extra, none missing) |

**Noise is the difficulty dial.** Each secret is embedded in `noise` real Enron distractor emails
(0 → 600+); the clues are always kept, only the haystack grows. Every `model × config × noise` cell is
repeated (default 3 reps, a different haystack seed each) and averaged over the 9 secrets. A 1M-context
model reads the full 600-email pile; a 200K model truncates and its high-noise points are flagged
`trunc` (and dropped, not compared as a true reading).

```bash
# one tester, full sweep, fixed Sonnet judge
uv run python scripts/run_eval.py --engine api --preset openai/gpt-5.4 \
    --clues benchmark_pool/emails_lying_n2.jsonl:n2,benchmark_pool/emails_lying_n3.jsonl:n3 \
    --noise 0,100,300,600 --reps 3 --judge-preset anthropic/claude-sonnet-4.6 \
    --max-ctx 1000000 --parallel 8

# a long-context LOCAL open model (free): raise the vLLM context so noise 600 is not truncated
uv run python scripts/run_eval.py --engine vllm --preset gemma4-31b --tp 4 \
    --model-len 240000 --max-ctx 240000 --noise 0,100,300,600 --reps 3
```

`--no-judge` runs the tester alone and saves each cell's `secret` text + deterministic recall/precision
(judging deferred); `scripts/judge_pass.py --dir <out>` fills `secret_match` / `final` later — so a free
local tester can run while a paid judge is rate-limited.

**Figures** (`scripts/plot_results.py` → `results/eval_final/plots/`):
- **A — `A_curves.png`**: FINAL vs noise, faceted n2 | n3 with ±SEM bands — ranking + degradation.
- **B — `B_noise{0,100,300,600}.png`**: score breakdown per noise (n2 | n3). Each bar = 1.0, split into
  *recovered · right-secret-but-weak-evidence · found-but-WRONG-secret · never-detected* — shows exactly
  **where** a model leaks (e.g. flash/haiku "find" a concealment at every noise but name the wrong one).
- **C — `C_heatmap.png`**: leaderboard heatmap, mean FINAL by model × config × noise.

---

## Cost / LLM Budget

Cost to **build** the benchmark (Stage 1 + 2), at OpenRouter list prices. Separation of duties:
generate = Sonnet 4.6 ($3/$15); blind judge / AND-probe = GPT-5.4 ($2.5/$15) + Gemini-3.1-Pro
(≈$1.25/$10) — the generator never grades its own secret.

- **Stage 1 (topics + specs).** Ground each topic on a real anchor (HyDE + BM25 + a fit-judge gate),
  then decompose it into the `a1/a2/a3` SPEC behind a blind spec-judge. Specs are cached and reused
  across `n`.
- **Stage 2 (clue emails).** One render call from the SPEC + the n-template, then a blind AND-check
  (every proper subset must stay innocent **and** the full set must recover) → diagnose → re-render
  loop (a few iterations).

Roughly **$0.3–0.5 per secret** at n = 2/3, so ≈ **$3–5 for 9 secrets**. Assembly (embedding clues in
real corpus noise) is pure CPU ($0).

Notes:
- **Gemini-3.1-Pro is a reasoning prober**: it emits chain-of-thought, so probe/match `max_tokens` must
  stay high (3000 / 1500) or its JSON truncates and it silently returns nothing.
- **Specs are cached**: an n-sweep (2 → 3) does not re-pay the spec-generation cost.

### Stage 3 — running the eval (per tester model)

Cost of the **full sweep** — n2+n3 (9 secrets each) × noise {0,100,300,600} × 3 reps — for one tester,
at OpenRouter list prices. Input tokens dominate (a noise-600 pile ≈ 200K tokens); the shared Sonnet
judge adds only ~$0.5/model. Reasoning testers (gpt-5.4, gemini-2.5-pro, r1) show a range for their
chain-of-thought tokens.

| tester | in / out ($/M) | context | full-sweep ~cost |
|---|---|---|---|
| openai/gpt-5.4 | 2.5 / 15 | 1M | **$41–48** |
| google/gemini-2.5-pro | 1.25 / 10 | 1M | **$22–26** |
| google/gemini-3.5-flash | 1.5 / 9 | 1M | **~$16** |
| anthropic/claude-haiku-4.5 | 1 / 5 | 200K † | **~$16** |
| deepseek/deepseek-r1 | 0.7 / 2.5 | 164K † | **$9–10** |
| deepseek/deepseek-v4-pro | 0.435 / 0.87 | 1M | **~$7** |
| google/gemini-2.5-flash | 0.3 / 2.5 | 1M | **~$5** |
| `gemma4-31b` (local, tp=4, 256K) | free | 256K | **$0** (GPU only) |

† 200K/164K models truncate at noise 600 (drop that cell). To cap spend, expensive flagships can be
sampled only at the single hardest noise (e.g. `--noise 600`) instead of the full sweep. One full
benchmark round here — build + n=3 regeneration + smoke tests + the multi-model eval — came to ≈ **$70**.

---

## Dataset

The pipeline operates on `data/enron_10/` — a 10-person subset of the Enron corpus selected by greedy
connectivity (maximising intra-group email volume).

| Person | Emails sent | Avg words/email |
|---|---|---|
| Mark Taylor | 313 | 137.9 |
| Sara Shackleton | 288 | 121.2 |
| Tana Jones | 232 | 124.4 |
| Steven Kean | 207 | 61.0 |
| Carol Clair | 141 | 123.0 |
| Jeff Dasovich | 90 | 178.4 |
| Richard Sanders | 81 | 153.0 |
| Elizabeth Sager | 74 | 140.6 |
| Susan Scott | 61 | 172.0 |
| Kay Mann | 45 | 57.5 |

---

## File Structure

```
enron_benchmark/
├── pyproject.toml
├── .env                            # API keys (not committed)
├── .env.example
│
├── prompts/                        # one .md per generative sub-step ({type}=lying; pluggable)
│   ├── topic_judge_lying.md        # Spec [1]: secret-first lying gate (5 checks; via TypeChecker) ← current
│   ├── spec_generate_lying.md      # Spec [2]: topic → canonical SPEC (a1/a2/a3)               ← current
│   ├── spec_judge_lying.md         # Spec [2]: gate the SPEC decomposition (faithful + a1/a2/a3) ← current
│   ├── clue_render.md              # Email: render n clue emails from SPEC + assignment        ← current
│   ├── eval_solve.md               # Eval: tester form {found, secret, evidence_email_ids}     ← current
│   ├── eval_judge.md               # Eval: judge stated secret vs answer key (fact+dir+actor+victim) ← current
│   ├── email_probe.md              # Email: blind solo / joint probe
│   ├── email_match.md              # Email: match a blind reading against the answer key
│   └── email_diagnose.md           # Email: pick failure modes + one revision
│
├── scripts/
│   ├── ground_topics.py            # Stage 1: seed lying topics + retrieve real anchors
│   ├── ground_finalize.py          # Stage 1: finalize the topic pool (CPU)
│   ├── plot_assemble.py            # shared helpers (scrub_corp, make_relabel)
│   ├── spec_build.py               # Stage 1[2]+2 entry: SPEC gen ⇄ judge → plan(n) → render ⇄ AND-check
│   ├── email_generate.py           # AND-check helpers (validate / diagnose / probe / match)
│   ├── email_finalize.py           # assemble: bind Person A–J → identities, embed in corpus (CPU)
│   ├── reground.py                 # re-ground anonymous labels → real Enron names at save time
│   ├── run_eval.py                 # Stage 3: tester → {found,secret,evidence} → Sonnet judge → score
│   ├── judge_pass.py               # Stage 3: deferred judging for a --no-judge run
│   ├── plot_results.py             # Stage 3: render figures A / B / C
│   ├── redo_n3.py                  # regenerate specific topics at genuine n=3
│   └── recheck_and.py              # independently re-verify AND on the shipped files
│
├── src/
│   ├── models/                     # engine abstraction (shared by every runner)
│   │   ├── engine_factory.py       # build_engine("api"|"vllm", preset)
│   │   ├── api_engine.py           # APIEngine: OpenAI-compatible, presets, retry
│   │   └── vllm_engine.py          # VLLMEngine: local vLLM, MODEL_CONFIGS presets
│   │
│   └── grounding/                  # Stage-1 grounding: topic → real anchor
│       ├── corpus.py               # load the 10-person corpus
│       ├── retrieval.py            # hybrid HyDE + BM25 retriever
│       ├── prompts.py              # topic-gen, HyDE, fit-judge prompts
│       ├── check.py                # Sonnet anchor-fit checker
│       └── pipeline.py             # propose_topic / propose_grounding
│
├── benchmark_pool/
│   ├── people.json                 # cast roster: Person A–J ↔ real Enron identities
│   ├── style_bank.json             # per-persona voice cards (Stage 2 re-voicing)
│   ├── topics_lying.json           # Stage 1 output — grounded lying topics + real anchors
│   ├── specs_lying.jsonl           # Stage 2 output — per-topic SPEC (a1/a2/a3 + answer_key)
│   ├── emails_lying_n2.jsonl       # benchmark @ n=2 clues            (+ .txt)
│   └── emails_lying_n3.jsonl       # benchmark @ n=3 clues, genuine distributed  (+ .txt)
│
├── results/eval_final/             # Stage 3: <model>/{raw,summary}.csv + plots/{A_curves,B_noise*,C_heatmap}.png
│
├── data/
│   └── enron_10/                   # 10-person subset
│       ├── threads.jsonl
│       └── by_person/{firstname.lastname}/{sent,participated}.jsonl
│
└── docs/pipeline_v2.md             # canonical living spec
```

---

## Setup

**Requirements:** Python ≥ 3.10, [uv](https://github.com/astral-sh/uv)

```bash
uv sync                 # core (API mode)
uv sync --extra vllm    # also install vLLM for local inference
```

Copy `.env.example` to `.env` and fill in credentials:

| Provider | Variables |
|---|---|
| OpenRouter | `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL` |
| Google Gemini | `GOOGLE_API_KEY`, `GOOGLE_BASE_URL` |
| Any OpenAI-compatible | `OPENAI_API_KEY`, `OPENAI_BASE_URL` |

---

## Running the Pipeline

Every runner takes `--engine {api,vllm}` (shared `src/models/engine_factory.py`), so any step can run
on a pinned closed model (reproducible) or a local vLLM model.

### Stage 1 — ground topics on real anchors

```bash
# Seed abstract lying secrets → HyDE + BM25 retrieve a real Enron anchor → type-gate.
uv run python scripts/ground_topics.py --secret-type lying \
    --out benchmark_pool/topics_lying.json
```

### Stage 2 — SPEC → clue emails   (main entry: spec_build.py)

`spec_build.py` does it all: SPEC gen ⇄ blind spec-judge → deterministic clue→atom plan for `n` → one
render call → blind AND-check (subset-leak + joint-recovery) → diagnose → re-render loop.

```bash
uv run python scripts/spec_build.py \
    --topic all --n 3 --secret-type lying \
    --plots       benchmark_pool/topics_lying.json \
    --specs-file  benchmark_pool/specs_lying.jsonl \
    --preset        or-claude-sonnet \
    --judge-preset  or-gpt-5 \
    --probe-presets or-gpt-5,google/gemini-3.1-pro-preview \
    --budgets 3,5 \
    --out benchmark_pool/emails_lying_n3.jsonl
```

| Flag | Default | Description |
|---|---|---|
| `--topic` / `--matrix` | `all` | one topic (`T07`), `all`, or a per-topic n matrix (`T02:3,T08:2`) |
| `--n` | 2 | clue emails per secret (the SPEC is reused across `n`) |
| `--preset` | `or-claude-sonnet` | generator (SPEC + clue emails) |
| `--judge-preset` | `or-gpt-5` | blind SPEC-judge (cross-vendor) |
| `--probe-presets` | gpt-5 + gemini | joint / subset-leak AND-probers (recover if ANY does) |
| `--budgets` | `3,5` | render-retry budget (plot fixed once; only the email step retries) |
| `--engine` | `api` | `vllm` = one local model for gen+judge+probe (smoke only) |
| `--out` | `emails_lying_n<n>.jsonl` | benchmark output; `<out>.attempts.json` logs every attempt |

Assembly (embedding the clue emails in `noise` real Enron emails + building the answer key) happens
inside the eval at read time (`email_finalize.build_haystack`), so there is no separate assemble step.

### Stage 3 — evaluate a model

```bash
uv run python scripts/run_eval.py --engine api --preset openai/gpt-5.4 \
    --clues benchmark_pool/emails_lying_n2.jsonl:n2,benchmark_pool/emails_lying_n3.jsonl:n3 \
    --noise 0,100,300,600 --reps 3 --judge-preset anthropic/claude-sonnet-4.6 \
    --parallel 8 --max-ctx 1000000

uv run python scripts/plot_results.py     # figures A / B / C from results/eval_final/
```

---

## Output Format

### Stage 1 — `benchmark_pool/topics_lying.json`

`kept[]` holds one grounded topic per entry: the topic, the real anchor email it sits on, and the
anchor body (kept so the eval can later excise the true event from the haystack).

### Stage 2 SPEC — `benchmark_pool/specs_lying.jsonl`

One SPEC per line — the decomposed definition of the secret. The conclusion lives ONLY in `answer_key`;
the `a1/a2/a3` atom facts never state it:

```jsonc
{
  "topic_id": "T02",
  "spec": {
    "actor": "Person C", "victim": "Person B",
    "counterparty": "...", "matter": "...", "era": "2000-12",
    "answer_key": { "true_fact": "...", "false_belief": "..." },
    "a1": { "role": "true_state",      "fact": "no master agreement / diligence incomplete as of 12/7" },
    "a2": { "role": "knew",            "fact": "Person C knows a1" },
    "a3": { "role": "false_statement", "fact": "Person C tells Person B it is approved to trade" },
    "reliance_rule": "Person B forwards the approval and never re-checks"
  }
}
```

### Stage 2 benchmark — `benchmark_pool/emails_lying_n<n>.jsonl`

One record per topic (already re-grounded to real Enron identities):

```jsonc
{
  "topic_id": "T02", "status": "KEPT", "n": 3, "secret_type": "lying",
  "check": { "joint": "2/2", "leaks": [] },        // blind AND-check: full set recovers, no subset leaks
  "answer": {                                      // the graded answer key
    "concealment": "...", "actor": "Tana Jones — ...", "victim": "Sara Shackleton — ...",
    "true_fact": "...", "false_belief": "..."
  },
  "atoms": [ { "id": "a1", "role": "true_state", "fact": "..." } /* a2, a3 */ ],
  "clues": [
    { "i": 1, "carries": ["a1"],
      "messages": [ { "from": "Mark Taylor", "to": ["..."], "date": "2000-12-07",
                      "subject": "...", "body": "..." } ] }
    // ... n clues; a1 (truth) and a3 (false statement) never share a clue
  ],
  "_anchor": { "message_id": "...", "text": "..." }  // held out — lets the eval excise the real event
}
```

`<out>.attempts.json` keeps every render iteration (clues + the blind AND-report + the diagnoser's
`{modes, revision}`) — the full trail for why a topic converged or dropped.

---

## Model Presets

### API presets (`--engine api`)

Named presets (`src/models/api_engine.py`); any raw OpenRouter slug also works directly as a preset
(sent on `OPENROUTER_*` credentials):

| Preset / slug | Model | Role |
|---|---|---|
| `or-claude-sonnet` | anthropic/claude-sonnet-4.6 | generator · **fixed eval judge** |
| `or-gpt-5` | openai/gpt-5.4 | blind SPEC-judge / AND-probe / diagnose |
| `or-gemini-pro` | google/gemini-3-pro | cross-vendor AND-probe |
| raw slug | `google/gemini-2.5-flash`, `anthropic/claude-haiku-4.5`, `deepseek/deepseek-v4-pro`, `openai/gpt-5.4`, `google/gemini-2.5-pro`, … | eval testers |

### vLLM presets (`--engine vllm`)

`gemma4-31b` (256K context, TP 2 — use `--tp 4 --model-len 240000` to read a noise-600 haystack
un-truncated), `gemma4-26b`, `gemma3-27b/12b`, `qwen3.5-27b` / `qwen3.6-27b` (262K), `qwen3-32b`,
`qwen3-235b-fp8` (TP 4), `gpt-oss-120b` (TP 4). A 31B model needs TP ≥ 2 on A800 40 GB; `--model-len`
overrides the preset's default 32K context cap for long-haystack reads.

---

## References

The architecture draws on the following works; each row maps a source to the design choice it informs.

### Method — retrieval · atomization · iterative refinement

| # | Paper | Used in |
|---|---|---|
| 1 | **MuSiQue: Multihop Questions via Single-hop Question Composition.** Trivedi et al., *TACL* 2022. [arxiv/2108.00573](https://arxiv.org/abs/2108.00573) | The blind AND-validation pass condition (full set recovers the secret **AND** no proper subset does) is MuSiQue's single-hop-sufficiency filter applied at the clue level. |
| 2 | **FActScore: Fine-grained Atomic Evaluation.** Min et al., *EMNLP* 2023. [arxiv/2305.14251](https://arxiv.org/abs/2305.14251) | Atomize each concealment into role-tagged atoms so every clue can be rendered, observed, and verified independently. |
| 3 | **Reflexion: Language Agents with Verbal Reinforcement Learning.** Shinn et al., *NeurIPS* 2023. [arxiv/2303.11366](https://arxiv.org/abs/2303.11366) | The diagnoser's `{failure modes, revision}` output is Reflexion-style verbal feedback fed back into the next distribution pass. |
| 4 | **Self-Refine: Iterative Refinement with Self-Feedback.** Madaan et al., *NeurIPS* 2023. [arxiv/2303.17651](https://arxiv.org/abs/2303.17651) | Both gates — the plot judge loop and the email diagnose loop — follow generate → structured critique → revise → re-evaluate. |
| 5 | **Judging LLM-as-a-Judge with MT-Bench / Chatbot Arena.** Zheng et al., *NeurIPS* 2023. [arxiv/2306.05685](https://arxiv.org/abs/2306.05685) | Separation of duties: the generator never probes or judges; blind probers / judge are different vendors, run without the intended answer in context. |
| 6 | **Large Language Models Cannot Self-Correct Reasoning Yet.** Huang et al., *ICLR* 2024. [arxiv/2310.01798](https://arxiv.org/abs/2310.01798) | Why the feedback signal is external and blind — the prober/diagnoser is a separate model reading the clues cold, not the generator grading its own work. |

### Concealment — law & social theory

What *counts* as a deliberate concealment, and how one is structured, is grounded in the law of
misrepresentation and the sociology of secrecy — not invented ad hoc.

| # | Source | Informs |
|---|---|---|
| 7 | **Georg Simmel, "The Sociology of Secrecy and of Secret Societies."** *American Journal of Sociology* 11(4), 1906. | The secret as a *social form* whose content is partitioned and access-controlled across a network — the basis for distributing one concealment over several people's emails rather than one message. |
| 8 | **Erving Goffman, *The Presentation of Self in Everyday Life*.** 1959. | Impression management / information control: the actor governs what the victim can infer; the false assurance `a3` is a front-stage performance for the victim. |
| 9 | **Paul Ekman, *Telling Lies*.** 1985. | Deception splits into **falsification** (asserting `¬F`) and **concealment** (withholding `F`). `lying` builds out falsification end-to-end; *omission* / *half-truth* are the concealment-family secret-types on the roadmap. |
| 10 | **Sissela Bok, *Lying* (1978) / *Secrets* (1982).** | The moral and structural line between an *active lie* and a *kept secret* — why a secret-type must fix a **positive, quotable act** (not mere silence) for the concealment to count as deliberate. |
| 11 | **Rogers, Zeckhauser, Gino, Norton & Schweitzer, "Artful Paltering."** *J. Personality & Social Psychology* 112(3), 2017. | Paltering — misleading with technically-true statements — as a distinct mechanism, motivating a future `paltering` secret-type separate from outright lying. |
| 12 | **U.S. securities-fraud doctrine:** SEC Rule 10b-5; *TSC Industries v. Northway*, 426 U.S. 438 (1976) (materiality); *Ernst & Ernst v. Hochfelder*, 425 U.S. 185 (1976) (scienter); Restatement (2d) of Torts §551 (non-disclosure). | The gates: **materiality** (a reasonable person would act on it) = the `reliance_rule`; **scienter** (the actor *knew*) = the `a2` "knew" atom and the deliberateness requirement; **misstatement vs. omission** = the `lying` vs. `omission` secret-types. |
