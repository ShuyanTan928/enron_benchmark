# Contributing

Thanks for your interest. This repository hosts a benchmark; contributions typically fall into
bug fixes, new evaluation adapters, or additions to the construction pipeline.

## Development setup

```bash
uv sync                      # or: pip install -r requirements-dev.txt  (skips vllm)
uv run pytest -q             # run the test suite
```

Provide an OpenRouter/OpenAI-compatible key in `.env` (see `.env.example`) only for stages that
call a model; the tests run without any key.

## Before opening a PR

- `uv run pytest -q` passes.
- New behavior has a test (see `tests/`).
- No secrets, API keys, or raw Enron `maildir` are committed (`.gitignore` guards these).
- Prompt changes keep `prompts/README.md` and `prompts_review.md` in sync.

## Benchmark integrity rules

These keep the benchmark trustworthy — please respect them:

- **No hand-editing of cases.** Cases enter the set only through the automated pipeline and its
  AND-check. Do not manually fix, select, or drop individual cases.
- **No rules derived from specific cases.** Construction/validation criteria must be general, not
  reverse-engineered from a particular example.
- **Human judgments stay an audit.** Human review is used to *measure* quality, never to filter or
  select cases.
- **Separation of duties.** The generator, the blind prober, and the judge must remain different
  models.

## Reporting data concerns

If you are represented in the underlying Enron corpus and want a record excluded, open an issue and
we will add it to the exclusion list. See `DATA_CARD.md`.
