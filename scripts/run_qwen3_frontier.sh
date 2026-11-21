#!/usr/bin/env bash
# Add the full frontier rule to the Qwen3-8B experiment (only its 5 lineages train), then re-run the
# official BIRD dev evaluation of ALL Qwen3 round-3 adapters in one session, so every rule is compared
# within a single evaluation run (earlier results kept as eval_greedy_prev). Run inside tmux:
#   bash scripts/run_qwen3_frontier.sh --compile
set -euo pipefail
cd "$(dirname "$0")/.."
EXTRA="${1:-}"
CFG=configs/qwen3.yaml bash scripts/run_frontier.sh $EXTRA
if [ -d runs/qwen3/eval_greedy ] && [ ! -d runs/qwen3/eval_greedy_prev ]; then
  mv runs/qwen3/eval_greedy runs/qwen3/eval_greedy_prev
fi
python scripts/official_eval.py run    --config configs/qwen3.yaml --round 3 $EXTRA >> runs/qwen3_official2.log 2>&1
python scripts/official_eval.py report --config configs/qwen3.yaml --round 3 > runs/qwen3_official_report2.log 2>&1
cat runs/qwen3_official_report2.log
