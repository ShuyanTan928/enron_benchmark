# Enron Benchmark

A two-stage pipeline that builds a **distributed-clue deception-detection benchmark** from the Enron
email corpus. Each item hides a deliberate concealment across several individually-innocuous emails:
no single email gives the secret away, but read together they reveal *who concealed what from whom*.
The benchmark measures whether an LLM can recover that hidden concealment from the joined evidence.

---

## Project Overview

The pipeline runs in two named stages. **Plot Generation** decides *what* each secret is and *where*
it lands on the real corpus; **Email Generation** turns each plot into the actual benchmark emails and
buries them in real Enron noise. Generation and validation are always split across vendors
(generate = Sonnet, judge / blind-probe = GPT-5.4 + others) so the model that writes a secret never
grades it.

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  STAGE 1 — PLOT GENERATION                          what the secret is + where ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Ground     seed an abstract concealment, then retrieve a real Enron email to  ║
║             anchor it — the anchor fixes the carrier deal + the era only.       ║
║                                                                                 ║
║  Plant      cast the concealment onto the anchor as a concrete plot (actor →    ║
║  (gen⇄judge) victim, true_fact vs false_belief, answer key). A blind judge      ║
║             gates it on seven checks; regenerate ≤ K, drop on failure.          ║
║                                                                                 ║
║   gen = Sonnet · judge = GPT-5.4                                                 ║
║   ⇒ deliverable:  benchmark_pool/plot_generation.json   (10 plots + answer key) ║
╚══════════════════════════════════════════════════════════════════════════════╝
                                     │
                                     ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║  STAGE 2 — EMAIL GENERATION                         the actual benchmark emails ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Atomize    break the concealment into role-tagged atoms                        ║
║             {true_state · knew · gain · false_assurance (· reliance)}.           ║
║             Atomized ONCE and cached — never regenerated in the loop.            ║
║                                                                                 ║
║  Distribute spread the atoms over N clue emails (true_state and false_assurance ║
║  → voice    never share a clue), then re-voice each in its sender's style.       ║
║                                                                                 ║
║  Validate   a blind prober checks every clue is innocuous ALONE and the secret  ║
║  (gen⇄       is recoverable JOINTLY. On failure a diagnoser names the failure    ║
║   diagnose) modes + one revision, fed back into distribution; regenerate ≤ K.   ║
║                                                                                 ║
║   gen = Sonnet · probe/match/diagnose = GPT-5.4 (+ Grok-4.3, Gemini-3.1)         ║
║   ⇒ deliverable:  benchmark_pool/email_generation_n2.jsonl  (+ _n3 at n=3)      ║
║                                                                                 ║
║  Assemble   bind Person A–J → real Enron identities, embed the clue emails in   ║
║  (CPU)      real Enron noise, interleave by date.                               ║
║   ⇒ deliverable:  data/benchmark/<TID>_haystack.jsonl  +  <TID>_answer.json     ║
╚══════════════════════════════════════════════════════════════════════════════╝
                                     │
                                     ▼
        Downstream eval:  model-under-test → jury → scores / plots
```

Each stage feeds the next: Plot Generation emits the plots + answer keys; Email Generation reads a
plot, distributes it into individually-ambiguous clue emails, validates that no clue leaks alone, and
plants them in the corpus to form one benchmark sample per secret. The canonical living spec is
[`docs/pipeline_v2.md`](docs/pipeline_v2.md).

---

## Stage 1 — Plot Generation

A **plot** is a concrete concealment cast onto a real Enron email. The answer key for each plot is the
five-part secret:

| field | meaning |
|---|---|
| `actor` | who conceals (anonymous label Person A–J) |
| `victim` | who is misled and acts on the false belief |
| `true_fact` / `false_belief` | a strict binary — F is true; the victim is led to believe ¬F |
| `either_or` | the two mutually-exclusive readings, stated plainly |
| `anchor` | the real Enron email (date + subject) the plot is grounded on |

**Ground.** Seed an abstract concealment, then retrieve a real Enron email as the anchor via hybrid
retrieval (HyDE + BM25) with a fit-judge gate (`NONE` if nothing genuine grounds it). The anchor
supplies only the carrier deal and the era — never the concealment itself.

**Plant (generate ⇄ judge).** Fill the plot template from the anchor and cast the concealment as a
concrete scene with a quotable false assurance. A **blind judge** (different vendor, never told the
intended answer) gates the plot on seven checks:

| check | requires |
|---|---|
| `check1_grounded` | recaps the anchor's real specifics + the binary; same deal, no drift |
| `check2_binary` | `true_fact` / `false_belief` are strict, externally-checkable opposites |
| `check3_casting` | both roles are anchor-email people, or a casting note justifies the reach |
| `check4_positive_act` | a quotable sentence asserts the false version — never silence/omission |
| `check5_material` | believing the false version makes the victim take a consequential action |
| `check6_consistent` | the concealer knows the truth; nothing in the plot admits it |
| `check7_localized` | one pointable concealment message + one reliance action |

Any non-PASS feeds the failing criteria back and regenerates (≤ K, default 3; exceeding K drops the
topic and logs why). Driven by the ~40% judge pass-rate, keeping 10 plots costs roughly 26 drafts.

---

## Stage 2 — Email Generation

Email Generation reads one plot and turns it into N clue emails that are innocuous alone but jointly
recover the concealment. It runs **atomize once, then a generate ⇄ diagnose loop** over the emails —
the atoms are never regenerated.

**Atomize (once, cached).** Break the concealment into the minimal role-tagged facts a reader needs:

| role | the atom states |
|---|---|
| `true_state` | what is actually the case (split into several atoms if the truth is rich) |
| `knew` | the truth was in the concealer's own hands (they ran it / were told / hold the file) |
| `gain` | the concrete cost the truth would trigger, written as a neutral fact |
| `false_assurance` | the concealer asserting the opposite, with no honest reading |
| `reliance` *(optional)* | a consequential action the victim takes *because* they believe the lie |

Atoms are written to `email_generation_atoms.jsonl` and **never regenerated** — re-running a topic at a
different `n` reuses them.

**Distribute → voice.** Spread the atoms over exactly N clue emails (hard rule: `true_state` and
`false_assurance` never share a clue), then re-voice each email in its sender's persona style.

**Validate (blind) → diagnose → iterate.** Probers that never saw the answer key check two properties:

- **solo-leak** — no single clue (default prober GPT-5.4) reveals the concealment on its own;
- **joint-recovery** — the full set jointly recovers actor/victim/secret (3-prober ensemble
  GPT-5.4 + Grok-4.3 + Gemini-3.1, majority 2/3).

On failure a **diagnoser** classifies which of eight failure modes apply and writes one overall
revision; *all feedback goes only to the distribution step* — the emails are rewritten, the atoms are
not. The eight modes:

```
SOLO_LEAK · SUBSET_LEAK · WRONG_VICTIM · WRONG_ACTOR
MISSING_true_state · MISSING_knew · MISSING_gain · WEAK_FALSE_ASSURANCE
```

A `MISSING_*` mode means *that atom exists but isn't written into any email* — surface it; it never
means invent a new atom. The loop regenerates the emails (≤ K, default 5 for borderline topics) and
re-validates; on success the topic is kept, otherwise dropped and logged.

**Assemble (CPU).** Bind each Person A–J label to its real Enron identity (`people.json`), embed the
clue emails in real corpus noise, and interleave by date into one haystack + answer key per topic.

> Identities: Stage 1/2 reason over anonymous labels so no fabricated concealment touches a real
> identity *during generation*; the final assembled dataset re-grounds `[firm] → Enron` and
> Person A–J → the real cast (`benchmark_pool/people.json`).

---

## Cost / LLM Budget

End-to-end cost to build the benchmark from scratch (10 secrets), at OpenRouter list prices
(Sonnet 4.6 $3/$15, GPT-5.4 $1.25/$10, Grok-4.3 ≈$3/$15, Gemini-3.1-Pro ≈$1.25/$10 per M in/out).

**Stage 1 — Plot Generation, one-time.** Driven by the ~40% judge pass-rate: to keep 10 plots the run
generated + judged **26** (grounding ≈ 3 Sonnet calls/proposal + plot gen on Sonnet + the seven-check
judge on GPT-5.4).

| | Sonnet (gen) | GPT-5.4 (judge) | total |
|---|---|---|---|
| Plot Generation (→ 10 kept) | ~$2.25 | ~$0.36 | **~$2.6** |

**Stage 2 — Email Generation, by clue-count `n`.** Per topic: atomize ×1 (cached) → distribute + voice
(Sonnet) → solo-leak probe (GPT-5.4, per clue) → joint probe (GPT-5.4 + Grok-4.3 + Gemini-3.1, majority
2/3). Assumes the measured avg of **1.7 iterations**.

| `n` (clues) | Sonnet | GPT-5.4 | Grok-4.3 | Gemini-3.1 | $/topic | **$ / 10 topics** |
|---|---|---|---|---|---|---|
| 2 | 0.111 | 0.020 | 0.014 | 0.066 | 0.21 | **~$2.1** |
| 3 | 0.152 | 0.026 | 0.014 | 0.066 | 0.26 | **~$2.6** |
| 4 | 0.193 | 0.033 | 0.015 | 0.067 | 0.31 | **~$3.1** |

**Whole pipeline (plot + email @ n=2) ≈ $4.7** for 10 secrets. Assembly is pure CPU ($0).

Notes:
- The hidden cost driver in Stage 1 is the **40% judge pass-rate** — 26 drafts for 10 keepers;
  raising the plot judge's first-pass rate saves more than any Stage-2 tuning.
- **Gemini-3.1-Pro is a reasoning model**: it emits ~2.5k tokens of chain-of-thought per probe, so it
  costs about as much as all of Sonnet's voice work despite running once per iteration. Its cost is
  **flat across `n`** (the joint probe runs once/iter regardless of clue count). Probe/match
  `max_tokens` must stay high (3000 / 1500) or its JSON truncates and it silently returns nothing.
- **Atoms are cached**: an n-sweep (2 → 3 → 4) does not pay the atomize cost three times.

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
├── prompts/                        # one .md per generative sub-step
│   ├── secret_plot_from_carrier.md # Plot: plant the concealment onto the anchor (template)
│   ├── secret_plot_judge.md        # Plot: blind judge, the seven checks
│   ├── clue_atomize.md             # Email: break the concealment into role-tagged atoms
│   ├── clue_distribute.md          # Email: spread atoms over N clue emails
│   ├── email_voice.md              # Email: re-voice a clue in its sender's style
│   ├── email_probe.md              # Email: blind solo / joint probe
│   ├── email_match.md              # Email: match a blind reading against the answer key
│   └── email_diagnose.md           # Email: pick failure modes + one revision
│
├── scripts/
│   ├── ground_topics.py            # Plot: seed topics + retrieve real anchors
│   ├── ground_finalize.py          # Plot: finalize the topic pool (CPU)
│   ├── plot_assemble.py            # Plot: fill the plot template (+ shared helpers: scrub_corp, relabel)
│   ├── plot_iterate.py             # Plot: generate plot + judge (seven checks) loop
│   ├── plot_generate.py            # Plot: fused grounding + plot + judge driver → plot_generation.json
│   ├── email_assemble.py           # Email: fill the clue template
│   ├── email_generate.py           # Email: atomize → distribute → voice → blind AND-validate → diagnose
│   ├── email_finalize.py           # Email: bind Person A–J → identities, embed in corpus (CPU)
│   ├── email_readable.py           # Email: render clue JSONL → readable .txt
│   ├── email_diagnose.py           # Email: standalone diagnose-loop validator
│   └── run_pipeline.py             # end-to-end demo (plot → email → assemble)
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
│   ├── plot_generation.json        # Stage 1 output — 10 plots + answer keys
│   ├── plot_generation.txt         #   human-readable companion
│   ├── email_generation_atoms.jsonl    # cached role-tagged atoms (n-independent)
│   ├── email_generation_n2.jsonl   # Stage 2 output @ n=2 clues  (+ .txt, + .attempts.json)
│   └── email_generation_n3.jsonl   # Stage 2 output @ n=3 clues  (+ .txt, + .attempts.json)
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

Every runner takes `--engine {api,vllm}` (shared `src/models/engine_factory.py`), so generation can run
on a pinned closed model (reproducible) or a local vLLM model.

### Stage 1 — Plot Generation

```bash
# Fused driver: ground each topic on a real anchor, plant the plot, judge it (seven checks).
uv run python scripts/plot_generate.py \
    --gen-engine api  --gen-preset  or-claude-sonnet \
    --judge-engine api --judge-preset or-gpt-5 \
    --people benchmark_pool/people.json \
    --out benchmark_pool/plot_generation.json
```

The modular path (`ground_topics.py` → `ground_finalize.py` → `plot_assemble.py` → `plot_iterate.py`)
exists for running each sub-step separately; `plot_generate.py` is the one-shot driver.

### Stage 2 — Email Generation

```bash
# Atomize (once, cached) → distribute → voice → blind AND-validate → diagnose loop.
uv run python scripts/email_generate.py \
    --engine api --preset or-claude-sonnet \
    --probe-engine api \
    --probe-presets or-gpt-5,x-ai/grok-4.3,google/gemini-3.1-pro-preview \
    --solo-probe-presets or-gpt-5 \
    --topic all --n 2 --max-iters 5 \
    --out benchmark_pool/email_generation_n2.jsonl
```

| Flag | Default | Description |
|---|---|---|
| `--topic` | `all` | one topic id (e.g. `T07`) or `all` |
| `--n` | 2 | clue emails per secret (atoms are reused across `n`) |
| `--probe-presets` | `or-gpt-5` | joint-recovery ensemble (majority 2/3) |
| `--solo-probe-presets` | first joint | solo-leak prober(s) — cheap axis, default one model |
| `--diagnose-preset` | first joint | model that names failure modes + revision |
| `--max-iters` | 3 | regenerate budget before dropping a topic |
| `--atoms-file` | `…_atoms.jsonl` | cached atoms (use `--reatomize` to ignore) |
| `--out` | `…_n2.jsonl` | clue output; `<out>.attempts.json` logs every attempt |

```bash
# Human-readable companion (secret answer key + clue emails)
uv run python scripts/email_readable.py \
    --clues benchmark_pool/email_generation_n2.jsonl \
    --source benchmark_pool/plot_generation.json \
    --out  benchmark_pool/email_generation_n2.txt

# Assemble haystack + answer key (CPU, no model)
uv run python scripts/email_finalize.py --noise 100 ...
```

### End-to-end

```bash
# Demo: run plot → email → assemble for a couple of topics.
uv run python scripts/run_pipeline.py --topics T02,T05 --engine api --preset or-claude-sonnet --n 2
```

---

## Output Format

### Stage 1 — `benchmark_pool/plot_generation.json`

`kept[]` holds one entry per accepted plot; `discarded[]` records drops with the failing check.

```jsonc
{
  "id": "T01",
  "topic": "Credit limit already breached",
  "either_or": "Counterparty is within its approved credit limit  vs  has already exceeded it",
  "anchor": { "date": "2000-04-20", "subject": "EOL -Enserco Energy" },
  "plot": {
    "actor":  "Person C — credit coordinator who cleared the volume and conceals the breach",
    "victim": "Person D — trading desk liaison who relies on credit clearance",
    "true_fact":   "Enserco has already exceeded its approved credit limit ...",
    "false_belief":"Person D believes Enserco is still within its limit ...",
    "plot": "..."                       // the full scene
  }
}
```

### Stage 2 — `benchmark_pool/email_generation_n2.jsonl`

One JSON object per line (one record per topic):

```jsonc
{
  "topic_id": "T01",
  "status": "KEPT",                     // KEPT | DROP
  "atoms": [
    { "id": "A1", "role": "true_state",      "fact": "..." },
    { "id": "A4", "role": "false_assurance", "fact": "..." }
    // ... the cached, role-tagged atoms
  ],
  "clues": [
    {
      "i": 1,
      "carries": ["A1","A2","A3"],      // which atoms this clue encodes
      "messages": [
        { "from": "Person H", "to": ["Person I"], "cc": ["Person G"],
          "date": "2000-04-24", "subject": "...", "body": "..." }
      ]
    }
    // ... N clues; true_state and false_assurance never share a clue
  ]
}
```

`<out>.attempts.json` keeps every iteration: the generated clues, the blind probe/leak report, and the
diagnoser's `{modes, revision}` — the full transparency trail for why a topic converged or dropped.

---

## Model Presets

### API presets (`--engine api`)

| Preset | Model | Role |
|---|---|---|
| `or-claude-sonnet` | anthropic/claude-sonnet-4.6 | generator |
| `or-gpt-5` | openai/gpt-5.4 | judge / blind probe / diagnose |
| `or-gemini-pro` | google/gemini-3-pro | reviewer (alt) |
| `gemini-flash` / `gemini-pro` | gemini-2.0-flash / 2.5-pro | cheap utility calls |

Any raw OpenRouter slug also works directly as a preset (e.g. `x-ai/grok-4.3`,
`google/gemini-3.1-pro-preview` for the joint ensemble) — it is sent on `OPENROUTER_*` credentials.

### vLLM presets (`--engine vllm`)

`gemma4-31b` (TP 2), `gemma3-27b`, `gemma3-12b`, `qwen3-32b`, `qwen3-235b-fp8` (TP 4),
`gpt-oss-120b` (TP 4), `llama4-maverick-fp8` (TP 4). A 31B model needs TP ≥ 2 on A800s.

---

## References

The architecture draws on the following works; each row maps a paper to the design choice it informs.

| # | Paper | Used in |
|---|---|---|
| 1 | **MuSiQue: Multihop Questions via Single-hop Question Composition.** Trivedi et al., *TACL* 2022. [arxiv/2108.00573](https://arxiv.org/abs/2108.00573) | The blind AND-validation pass condition (full set recovers the secret **AND** no proper subset does) is MuSiQue's single-hop-sufficiency filter applied at the clue level. |
| 2 | **FActScore: Fine-grained Atomic Evaluation.** Min et al., *EMNLP* 2023. [arxiv/2305.14251](https://arxiv.org/abs/2305.14251) | Atomize each concealment into role-tagged atoms so every clue can be rendered, observed, and verified independently. |
| 3 | **Reflexion: Language Agents with Verbal Reinforcement Learning.** Shinn et al., *NeurIPS* 2023. [arxiv/2303.11366](https://arxiv.org/abs/2303.11366) | The diagnoser's `{failure modes, revision}` output is Reflexion-style verbal feedback fed back into the next distribution pass. |
| 4 | **Self-Refine: Iterative Refinement with Self-Feedback.** Madaan et al., *NeurIPS* 2023. [arxiv/2303.17651](https://arxiv.org/abs/2303.17651) | Both gates — the plot judge loop and the email diagnose loop — follow generate → structured critique → revise → re-evaluate. |
| 5 | **Judging LLM-as-a-Judge with MT-Bench / Chatbot Arena.** Zheng et al., *NeurIPS* 2023. [arxiv/2306.05685](https://arxiv.org/abs/2306.05685) | Separation of duties: the generator never probes or judges; blind probers / judge are different vendors, run without the intended answer in context. |
| 6 | **Large Language Models Cannot Self-Correct Reasoning Yet.** Huang et al., *ICLR* 2024. [arxiv/2310.01798](https://arxiv.org/abs/2310.01798) | Why the feedback signal is external and blind — the prober/diagnoser is a separate model reading the clues cold, not the generator grading its own work. |
