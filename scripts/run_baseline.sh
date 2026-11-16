#!/usr/bin/env bash
# Baseline results for all three datasets.
#   N=20 bash scripts/run_baseline.sh      <- cheap pilot first! (check cost per question)
#   bash scripts/run_baseline.sh           <- full run (N=100)
# Re-running is free: every call is cached in cache/llm_cache.sqlite.
set -euo pipefail
cd "$(dirname "$0")/.."

N="${N:-100}"
BUDGET="${BUDGET:-10}"

# GSM8K and MMLU-Pro: CoT, self-consistency at several costs, and debate (3 agents x 2 rounds = 9 calls).
# Self-consistency with k=3,6,9 draws the "same-cost" baseline curve that debate must beat.
for DS in gsm8k mmlu_pro; do
  python -m dj.run --dataset "$DS" --n "$N" --budget "$BUDGET" --ref "sc:k=9" \
    --methods cot "sc:k=3" "sc:k=6" "sc:k=9" "debate:n=3,r=2"
done

# JudgeBench: the judge, both answer orders.
##Commented out JudgeBench temporarily if we're only going to consider debate
#python -m dj.run --dataset judgebench --n "$N" --budget "$BUDGET" --methods judge "judge:k=3"

python -m dj.spend
