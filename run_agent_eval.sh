#!/usr/bin/env bash
# One-command setup + agent eval on a fixed 40-item sample, for one or more models.
#
# The 40 items cover every cell: commission/paltering x n=2/n=3 x work/casual
#   work topics   : T01 T02 T03 T04 T05   (energy-trading-desk secrets)
#   casual topics : T11 T12 T13 T14 T15   (a coworker's personal trouble)
#   -> 10 topics x 4 clue files = 40 items
#
# Usage:
#   export OPENROUTER_API_KEY=sk-or-...
#   ./run_agent_eval.sh <model-slug> [<model-slug> ...]
#
# Examples:
#   ./run_agent_eval.sh openai/gpt-4o
#   ./run_agent_eval.sh openai/gpt-4o anthropic/claude-sonnet-4.6 deepseek/deepseek-v4-pro
#   NOISE=400 JUDGE=openai/gpt-5-mini ./run_agent_eval.sh openai/gpt-4o google/gemini-2.5-pro
#
# Any OpenRouter model id works (Azure-routed ids too). Each model runs in turn and writes
# results/agent/<model>/rows.csv. Override the judge/noise with the JUDGE / NOISE env vars.
# Cost is ~40 items x tester + judge per model — a few dollars for a mid model at noise 200.
set -euo pipefail
cd "$(dirname "$0")"

[ "$#" -ge 1 ] || { echo "usage: OPENROUTER_API_KEY=... ./run_agent_eval.sh <model-slug> [<model-slug> ...]"; exit 1; }
: "${OPENROUTER_API_KEY:?set your key first:  export OPENROUTER_API_KEY=sk-or-...}"
JUDGE="${JUDGE:-openai/gpt-5.6-terra}"
NOISE="${NOISE:-200}"

# 1) install uv if missing
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

# 2) API-only environment (openai + dotenv + numpy) — skips the heavy local-GPU stack
uv venv .venv-api
uv pip install --python .venv-api "openai>=1.0.0" "python-dotenv>=1.0.0" numpy

# 3) OpenRouter credentials
cat > .env <<EOF
OPENROUTER_API_KEY=$OPENROUTER_API_KEY
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
EOF

CLUES="benchmark_pool/emails_commission_n2.jsonl:com_n2,benchmark_pool/emails_commission_n3.jsonl:com_n3,benchmark_pool/emails_paltering_n2.jsonl:pal_n2,benchmark_pool/emails_paltering_n3.jsonl:pal_n3"

# 4) run each model in turn (one failing model does not stop the rest)
set +e
for MODEL in "$@"; do
  OUT="results/agent/${MODEL//\//_}"
  echo "================  $MODEL   (judge=$JUDGE, noise=$NOISE)  ================"
  .venv-api/bin/python scripts/run_agent.py --engine api --preset "$MODEL" --judge-preset "$JUDGE" \
    --clues "$CLUES" \
    --topics T01,T02,T03,T04,T05,T11,T12,T13,T14,T15 \
    --noise "$NOISE" --anonymize benchmark_pool/pseudonyms.json --min-invest -1 \
    --out "$OUT"
  [ $? -eq 0 ] && echo "   -> $OUT/rows.csv" || echo "   !! $MODEL failed — continuing"
done

echo
echo "All done. Per-model scores in results/agent/*/rows.csv  (FINAL = found x secret-match x evidence)"
