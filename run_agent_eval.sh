#!/usr/bin/env bash
# One-command setup + agent eval on a fixed 40-item sample.
#
# The 40 items cover every cell: commission/paltering x n=2/n=3 x work/casual
#   work topics   : T01 T02 T03 T04 T05   (energy-trading-desk secrets)
#   casual topics : T11 T12 T13 T14 T15   (a coworker's personal trouble)
#   -> 10 topics x 4 clue files = 40 items
#
# Usage:
#   export OPENROUTER_API_KEY=sk-or-...
#   ./run_agent_eval.sh <model-slug> [judge-slug] [noise]
#
# Examples:
#   ./run_agent_eval.sh openai/gpt-4o
#   ./run_agent_eval.sh anthropic/claude-sonnet-4.6 openai/gpt-5-mini 400
#
# <model-slug> is any OpenRouter model id (Azure-routed ids work too). The judge
# defaults to a cross-vendor model; pass a different one as the 2nd argument.
# Cost is ~40 items x tester + judge — a few dollars for a mid model at noise 200.
set -euo pipefail
cd "$(dirname "$0")"

MODEL="${1:?usage: OPENROUTER_API_KEY=... ./run_agent_eval.sh <model-slug> [judge-slug] [noise]}"
JUDGE="${2:-openai/gpt-5.6-terra}"
NOISE="${3:-200}"
: "${OPENROUTER_API_KEY:?set your key first:  export OPENROUTER_API_KEY=sk-or-...}"

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

# 4) run the 40-item eval
OUT="results/agent/${MODEL//\//_}"
CLUES="benchmark_pool/emails_commission_n2.jsonl:com_n2,benchmark_pool/emails_commission_n3.jsonl:com_n3,benchmark_pool/emails_paltering_n2.jsonl:pal_n2,benchmark_pool/emails_paltering_n3.jsonl:pal_n3"
.venv-api/bin/python scripts/run_agent.py --engine api --preset "$MODEL" --judge-preset "$JUDGE" \
  --clues "$CLUES" \
  --topics T01,T02,T03,T04,T05,T11,T12,T13,T14,T15 \
  --noise "$NOISE" --anonymize benchmark_pool/pseudonyms.json --min-invest -1 \
  --out "$OUT"

echo
echo "Done — per-item scores: $OUT/rows.csv   (FINAL = found x secret-match x evidence)"
