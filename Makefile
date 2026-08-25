# Enron Distributed-Clue Deception Benchmark — common tasks.
# Model-calling targets need an OpenRouter/OpenAI-compatible key in .env (see .env.example).

.PHONY: help install test lint audit-human audit-style generate eval clean

help:
	@echo "make install       install test/dev dependencies (no vllm)"
	@echo "make test          run the test suite"
	@echo "make lint          run ruff (if installed)"
	@echo "make audit-human   build the human-audit packet from the benchmark"
	@echo "make audit-style   run the stylometric similarity audit"
	@echo "make generate      example: stream-generate cases (n=2) — needs API key"
	@echo "make eval          example: run one agent over the benchmark — set MODEL=, JUDGE="

install:
	pip install -r requirements-dev.txt

test:
	uv run pytest tests/ -q

lint:
	uv run ruff check scripts/ src/ tests/ || true

audit-human:
	uv run python scripts/human_audit_build.py --in-dir $(BENCH) --out-dir results/human_audit

audit-style:
	uv run python scripts/plot_clue_realism.py

# --- model-calling examples (override the variables as needed) ---
BENCH ?= benchmark_v2
MODEL ?= openai/gpt-5.6-luna
JUDGE ?= openai/gpt-5.6-terra

generate:
	uv run python scripts/stream_build.py --n 2 --n-work 25 --n-casual 25 --topic-budget 40 \
	  --gen-preset or-claude-sonnet --probe-presets $(JUDGE:terra=sol) \
	  --judge-preset $(JUDGE) --out-dir $(BENCH)

eval:
	uv run python scripts/run_inspect_agent_eval.py --model $(MODEL) --judge-model $(JUDGE) \
	  --noise 200 --out results/inspect/$(notdir $(MODEL))

clean:
	find . -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache
