# Data Card — Enron Distributed-Clue Deception Benchmark

Structured after *Datasheets for Datasets* (Gebru et al., 2021). This card documents the
benchmark's construction, contents, privacy handling, and intended use.

## Motivation

The benchmark studies **conjunctive secret recovery**: a target secret that no single email
reveals, but which can be inferred by combining clues distributed across several emails. It
measures whether an adversarial LLM agent can find that evidence inside a larger mailbox and
combine it to recover *who concealed what from whom*.

## Composition

- **Unit.** One *case* = a target secret + `n` clue email threads + an answer key, embedded in a
  sample of unrelated Enron background threads.
- **Size.** 100 cases: two clue counts (`n ∈ {2,3}`) × two mechanisms (commission, paltering),
  25 per cell — so clue-count and mechanism are each balanced 50/50. Register (work, casual) is
  balanced 25/25 within each clue count; inside a single cell the register split is 13/12. Built
  from 51 pooled scenarios (26 work / 25 casual).
- **Secret structure.** Each secret is placed on three fixed atoms — `a1` (an objective true
  state), `a2` (the actor knew `a1`), `a3` (the concealing act) — allocated to clues by a fixed
  template (`n=2`: `{a1,a2},{a3}`; `n=3`: `{a1},{a2},{a3}`).
- **What is synthetic vs. real.** The secrets, atoms, plots, clue emails, and answer keys are
  **synthetic** (LLM-generated for the benchmark). The **background** is real Enron mail; for work
  cases a real Enron email is used only as a *grounding carrier* during construction and is then
  removed from the evaluation archive.
- **Fields per case.** `topic_id`, `n`, `secret_type`, `answer.{secret,actor,victim}`, `atoms`,
  `clues[].messages[]` (from, to, cc, date, subject, body), plus an anchor reference for work cases.

## Collection & Construction

Fully automated (see `README.md` and the paper appendix for the pipeline):
topic → (work) grounding → atomization → plot → email → conjunctive AND-check.
A case is retained only when a blind prober (GPT-5.6 Sol) recovers the secret from the **full**
clue set **and** from **no proper subset**, with matches judged by a fixed judge (GPT-5.6 Terra).
Failed cases are diagnosed and regenerated (≤3 iterations) or dropped. No case is hand-edited or
hand-picked.

Background corpus: a threaded, processed subset of the public Enron corpus (`data/enron_10/`,
1,211 threads centered on ten Enron legal/regulatory employees).

## Privacy & Anonymization

The Enron corpus contains real people's mail. We take the following measures:

- **Pseudonymization** applied consistently to the mailbox, clue emails, and answer key before
  evaluation: personal names, email addresses, the `enron.com` domain, and recurring company/entity
  names are replaced with same-initial fictional stand-ins (`benchmark_pool/pseudonyms.json`). Dates
  and locations are retained.
- **Anchor excision.** For work cases, the grounding anchor and other threads about the same real
  event are removed from the eligible background pool, so the background never independently reveals
  the real matter used for construction.
- **Exclusion list.** A global drop list removes designated sensitive real records from the
  background pool.
- **Synthetic secrets.** All planted secrets are invented for the benchmark and are **not** claims
  about real Enron employees.

**Raw corpus is not redistributed.** Only the processed, pseudonymized derivative ships here; obtain
the original corpus from CMU (https://www.cs.cmu.edu/~enron/).

**Removal requests.** If you are a person represented in the underlying corpus and want a record
excluded, open an issue (or contact the maintainers) and we will add it to the exclusion list.

## Intended Use

- **In scope:** evaluating whether LLM agents can perform cross-record privacy inference; studying
  discovery vs. synthesis; ablations over archive size, clue count, register, and mechanism.
- **Out of scope / misuse:** this is a *defensive* measurement tool. It must not be used to profile,
  de-anonymize, or extract sensitive information about real Enron individuals, nor as a template for
  building real-world inference attacks on private archives. The threat model assumes an agent that
  *already* has read access; it does not model how such access is obtained.

## Licensing

- **Software** (code + prompts): MIT — see `LICENSE`.
- **Generated benchmark data** (secrets, atoms, plots, clue emails, answer keys): CC BY 4.0.
- **Enron-derived background:** original public-domain status (FERC/CMU); processed derivative only.

## Distribution & Versioning

Releases are versioned and frozen (git tag + a manifest listing case count and content hashes), so
every evaluation runs against the same snapshot. The frozen set lives in `data/benchmark/`
(`emails_{commission,paltering}_n{2,3}.jsonl` + `MANIFEST.json`).

## Known Limitations

- The conjunctive "no-subset-reveals" property is **operationalized relative to the prober model**
  (GPT-5.6 Sol): a stronger agent could in principle recover a secret from a subset the prober could
  not. It is not an absolute information-theoretic guarantee.
- The judge (GPT-5.6 Terra) is used both to filter cases during construction and to score agents at
  evaluation; a judge audit is reported separately to bound this dependence.
- The background corpus is limited to ~1.2k threads from ten employees, which caps the realistic
  archive size.
