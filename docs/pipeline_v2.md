# Enron Insertion Benchmark — Pipeline v2 (framework)

A living spec. Each step lists: **inputs**, **sub-steps + which model runs each**,
**deliverable (file + schema)**, and a **rubric** (how we decide the output is good,
and who checks it). Refine this file first; build after it's agreed.

## Runners (who executes a sub-step)
| tag | what | why |
|---|---|---|
| **CC** | Claude Code (subscription) | GENERATION + iterative feedback. Has memory → may know the secret → **must NOT judge or blind-probe**. |
| **OR-probe** | OpenRouter, stateless | BLIND solo/joint validation. **Never told the intended secret.** |
| **OR-jury** | OpenRouter, stateless | grades test-model answers vs gold. Different model than CC. |
| **OR-test** | OpenRouter / local vLLM | the models being benchmarked. |
| **CPU** | deterministic script | assembly, scoring, plots. Fully reproducible. |

## Standing principles
- **Separation of duties:** the model that GENERATES a secret never VALIDATES or JUDGES it. CC generates; OR-probe/OR-jury (stateless) check.
- **Blindness:** every solo/joint probe is run WITHOUT the intended secret in context — a stranger reading cold (this is the fix for the "leading the witness" bug).
- **A secret is binary + hard:** fact F is true/false and stable; the contradiction cannot be reconciled by timing / scope / degree (no "fixed since", "different item", "slow vs never").
- **PLOT-adapted (arXiv:2503.09780):** seeds expand to a cover story + clue facts via LLM with **diversity sampling** (N variants/seed), fighting homogeneity.
- **Reproducible:** every generative step has a prompt file under `prompts/`; outputs are files. Bit-exact repro = pin model+temp on OpenRouter. Every runner takes `--engine {vllm,api}` (shared `src/models/engine_factory.py`) so generation can run on a pinned closed model; the topic pool is finalized by `scripts/ground_finalize.py` (code, no hand assembly).

## Pipeline map
Two generative stages — **Plot Generation** (what the secret is + where) and **Email Generation**
(the actual benchmark emails) — then downstream eval.

| stage · sub-step | name | runner(s) | deliverable |
|---|---|---|---|
| Plot · ground | Topic seeds + real anchor | CC | `benchmark_pool/topics_v2.json` |
| Plot · plant | Plant secret into scene (+ iterate) | `plot_assemble` → `plot_iterate` (gen + judge check1–7) | `benchmark_pool/plot_generation.json` |
| Email · distribute | Atomize → distribute → AND blind-validation | `email_assemble` → `email_generate` | `benchmark_pool/email_generation_n2.jsonl` (+ `_n3`) |
| Email · assemble | bind labels→identities + embed in corpus | `email_finalize` (CPU, no model) | `data/benchmark/<TID>_haystack.jsonl` + `_answer.json` |
| eval 5 | Model-under-test eval | OR-test | `results/<run>/preds/` |
| eval 6 | Judging (jury) | OR-jury | `results/<run>/final/` + `scores.csv` |
| eval 7 | Scoring & plots | CPU | `results/<run>/plots/` + summary |

---

## Plot Generation · Ground (topic seeds + real anchor)
- **Input:** corpus distribution + secret criteria.
- **Sub-steps:** author 10 topics (9 work / 1 casual) — **CC** executing `prompts/generate_topics.md`.
- **Deliverable:** `benchmark_pool/topics_v2.json` (done).
- **Rubric (CC self-check):**
  - [ ] exactly 10; 9 `work` / 1 `casual` (matches measured ~90/10).
  - [ ] each topic expressible as the 5-part secret (binary F, hard incompatibility, concealment+motive, consequential, distributed).
  - [ ] every `concealment_shape` is UNIQUE (no near-duplicates); none is "hide a file in a private folder".
  - [ ] each `enron_anchor` quotes a real corpus phrase.

## Plot Generation · Plant the secret into a scene (gen ⇄ judge)
- **Input:** `benchmark_pool/topics_v2.json` (10 work topics, each with a real `enron_anchor`) + the anonymous roster `benchmark_pool/people.json`.
- **Flow:**

      plot_assemble.py              plot_iterate.py
      topic + anchor + team   ->   generate plot + key   ->   judge (check1–7)  --PASS-->  keep
        (fills the template)            (gen model)            (judge model)
                                             ^                       |
                                             |  feedback: failing criteria + fix
                                             +----------<--FAIL------+   (≤ K iters, then drop)

  1. `scripts/plot_assemble.py` fills the **pure generic** template `prompts/secret_plot_from_carrier.md` (SECRET + the real ANCHOR body + TEAM; cast names relabeled to Person A–J, company scrubbed) → `prompts/plot/<TID>.txt`. No per-topic content is hand-written — code fills placeholders only.
  2. `scripts/plot_iterate.py`: **GENERATE** the plot + answer key, then **JUDGE** it with `prompts/secret_plot_judge.md`; on any non-PASS, feed the failing criteria + fix back and **REGENERATE** (≤ K, default 3; exceed K → drop + log). Generator and judge are separate engines — judge defaults to reuse for local runs but should be a **different/stronger model in production** (e.g. Sonnet), keeping separation of duties.
- **Deliverable:** `benchmark_pool/plot_generation.json` — `kept[]` with `{topic_id, actor, victim, casting_note, true_fact, false_belief, plot}` (+ `discarded[]`). `<out>.attempts.json` keeps every gen+judge attempt for transparency.
- **Judge rubric (check1–check7; anonymization is OUT of scope):**
  - [ ] check1_grounded — recaps the anchor's real specifics + the `either_or` binary; same deal, no drift.
  - [ ] check2_binary — `true_fact` / `false_belief` are strict opposites, externally checkable.
  - [ ] check3_casting — both roles are anchor-email people, or `casting_note` genuinely justifies reaching out.
  - [ ] check4_positive_act *(load-bearing)* — a quotable sentence asserting the false version; never silence/omission.
  - [ ] check5_material — believing the false version makes the victim take a consequential action.
  - [ ] check6_consistent — concealer knows the truth; nothing in the plot (esp. the quoted line) admits it.
  - [ ] check7_localized *(load-bearing)* — one pointable concealment message + one reliance action.
  - **Gate:** every check PASS → keep; any WEAK/FAIL → regenerate; exceed K → drop and log why.

## Email Generation · Atomize → distribute → AND blind-validation (the QA gate)
- **Input:** one `plot` from `benchmark_pool/plot_generation.json` + the team roster + each author's persona card.
- **Note:** the concealment is **atomized once** into role-tagged facts (`true_state / knew / gain / false_assurance / reliance`, cached in `email_generation_atoms.jsonl`); the loop below only re-distributes those atoms into emails. On failure a diagnoser names which of 8 failure modes apply + one revision, fed into the next distribution pass — atoms are never regenerated.
- **Flow:**

      email_assemble.py                  email_generate.py
      secret + plot + voices   ->   split into N clues   ->   blind solo+joint probe + match  --PASS-->  keep
        (fills the template)            (gen model)           (probe model — never told the secret)
                                             ^                          |
                                             |   feedback: which clue leaked / why joint failed
                                             +----------<----FAIL-------+   (≤ K iters, then drop)

  1. `scripts/email_assemble.py` fills `prompts/clue_emails_from_plot.md`: the binary (true/false/either_or), the Step 2 plot, the **5 pieces** to distribute (true_state / knew / gain / false_assurance / reliance), the team **with each person's real persona card** (relabeled, company scrubbed), and the **anchor era** so clue dates land in the right period.
  2. The plot is split into **exactly N clues** (a clue = one email, or a chain of ≤ 2 emails counted as one): read ALONE each is unremarkable; read TOGETHER they reconstruct the concealment; drop ANY ONE and it can't be. THE TRUE STATE and THE FALSE ASSURANCE never share a clue.
  3. `scripts/email_generate.py` runs **AND blind-validation** with a *separate* prober that is never told the intended secret: `solo(clue_i)` must NOT recover the secret for every clue; `joint(all)` must recover it AND **match** the intended concealer + act + victim. Fail → feed back which clue leaked / why joint failed → REGENERATE (≤ K, default 3; exceed → drop + log). Generator ≠ prober (separation of duties).
- **Deliverable:** `benchmark_pool/email_generation_n2.jsonl` (+ `_n3` at n=3) — one JSON/line: `{topic_id, status, atoms:[…], clues:[{i, carries:[…atom ids…], messages:[{from,to,cc,date,subject,body}]}]}`. `<out>.attempts.json` keeps every attempt.
- **Rubric (gate = ALL true):**
  - [ ] every `solo(clue_i)` = NO secret recovered (innocuous alone).
  - [ ] `joint` independently recovers a secret that **matches** the intended concealer + act + victim.
  - [ ] no clue names the secret/deception or uses hide/conceal vocabulary; dates ordered & period-correct.
  - [ ] **gain** present (human criterion — the loss the lie avoids, tied to the concealer); not auto-gated.
  - **Gate:** any solo leak or joint mismatch → iterate; exceed K → drop the secret and log why.

## Email Generation · Assemble: bind labels→identities + embed into the corpus
- **Input:** `benchmark_pool/email_generation_n2.jsonl` + the corpus `data/enron_10/threads.jsonl` + `benchmark_pool/people.json` (label → identity map). **No model — fully deterministic (CPU).**
- **Sub-steps (`scripts/email_finalize.py`):**
  1. **Convert** each clue into full email records in the corpus's `threads.jsonl` schema: `message_id`, `from_addr`/`to_addrs`/`cc_addrs`, ISO `date` (an ordered send-time per message so chains sort right), `in_reply_to`/`references` (a ≤ 2-email chain becomes one 2-message thread), `word_count`.
  2. **Bind** Person labels → synthetic anonymized addresses (`Person A → person.a@firm.example`); the company is scrubbed to `[firm]` everywhere. (people.json's design: reason on labels through Steps 2–3, bind to an identity only at output — a real Enron identity or a pseudonym.)
  3. **Embed**: sample noise threads from the corpus, relabel them into the **same** anonymized namespace (the 10 cast → Person addresses, company → `[firm]`; stranger names tolerated), mix in the clue threads, and interleave every message by date into one mailbox — the needle buried in the haystack.
  4. **Answer key**: record which `message_id`s are the planted deception (per clue + its `carries`).
- **Deliverable:** `data/benchmark/<TID>_haystack.jsonl` (threads, detector-facing) + `data/benchmark/<TID>_answer.json` (ground truth — never shown to the test model).
- **Rubric (CPU asserts):**
  - [ ] every clue email present; clue dates plausible, period-correct, mixed into the noise (no `1980` placeholder leaking; no metadata tell).
  - [ ] one coherent anonymized namespace — no real cast name or company in any body; clue & noise addresses share the `@firm.example` form so the clues don't stand out.
  - [ ] deterministic given seed; the answer key lists exactly the planted `message_id`s.

## Step 5 — Model-under-test evaluation
- **Input:** assembled piles + the (de-biased, few-rule) test prompts.
- **Sub-steps:** run Detection / Identification / Grounding for each test model — **OR-test** (API models via OpenRouter; open models via local vLLM). Stateless, temp 0, k repeats.
- **Deliverable:** `results/<run>/preds/<model>__noise<N>.jsonl` (raw + parsed).
- **Rubric (operational, not quality):**
  - [ ] every sample answered; outputs parse to the expected fields.
  - [ ] no prompt leaks the answer; detection prompt is left/right symmetric (de-biased).
  - [ ] cost within the OpenRouter budget for this run (logged).

## Step 6 — Judging (jury)
- **Input:** test-model preds + gold (`data/benchmark/<TID>_answer.json` + the Step 2 plot/key).
- **Sub-steps:** jury scores detection / identification-match / grounding → per-gold 0–5 — **OR-jury** (stateless, ≠ CC). For multi-secret, bipartite match.
- **Deliverable:** `results/<run>/final/<model>__noise<N>.jsonl` (per-sample score, status) + `scores.csv`.
- **Rubric (must validate the jury itself):**
  - [ ] jury agrees with a human-labeled subset at **≥ 90%** (cf. AGENTDAM 98%); else fix the judge prompt.
  - [ ] scoring follows the 0–5 rubric deterministically (temp 0).
  - [ ] jury model ≠ generation model (no self-grading).

## Step 7 — Scoring & plots
- **Input:** `final/` scores.
- **Sub-steps:** seed-average, score-stacks, false-positive, per-secret difficulty — **CPU**.
- **Deliverable:** `results/<run>/plots/` + `summary.md`.
- **Rubric:**
  - [ ] seed-averaged (n = S × secrets per cell); FP reported alongside.
  - [ ] real-solver vs guesser separable (precision / FP axis); no artifact (e.g. spurious noise-peak) — if present, investigate before publishing.

---

## Model & cost allocation (OpenRouter ≈ $500/mo)
- **CC (flat / subscription):** Steps 1, 2(gen), 3(gen) — the heavy generation. ~free.
- **OR-probe:** Step 3 blind probes (solo/joint) — small (≈ N+1 probes per secret).
- **OR-jury:** Steps 3(match) + 6 — moderate.
- **OR-test:** Step 5 — **the main spend**; budget the eval sweep here (models × noise × seeds × 3 prompts). Reserve most of the $500 for this.

## Open decisions to set before building
1. Which OpenRouter models for **OR-probe**, **OR-jury**, and the **OR-test** roster? (and which open models stay on local vLLM)
2. Secrets per topic in Step 2 (1 vs N) and clue variants N in Step 3.
3. K = max blind-validation iterations before dropping a secret.
4. Noise levels + seed count for Step 4 (reuse 0,10,20,30,40,50,80,100 × 5 seeds?).
5. Human-labeled subset size for the Step-6 jury validation.
