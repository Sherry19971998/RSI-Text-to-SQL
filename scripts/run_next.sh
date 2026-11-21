#!/usr/bin/env bash
# Queue: (1) rare_first on the main model (only its new lineages train), then the official BIRD dev
# evaluation of ALL main-model round-3 adapters in one session (theta_0's EX moved ~1 point between
# evaluation sessions, so rules are only compared within a session; the earlier results are kept
# as eval_greedy_prev); (2) the Qwen3-8B experiment end to end. Run inside tmux:
#   bash scripts/run_next.sh --compile
set -euo pipefail
cd "$(dirname "$0")/.."
EXTRA="${1:-}"

# (1) main model + rare_first
CFG=configs/frontier.yaml bash scripts/run_frontier.sh $EXTRA
if [ -d runs/frontier/eval_greedy ] && [ ! -d runs/frontier/eval_greedy_prev ]; then
  mv runs/frontier/eval_greedy runs/frontier/eval_greedy_prev
fi
python scripts/official_eval.py run    --config configs/frontier.yaml --round 3 $EXTRA >> runs/frontier_official.log 2>&1
python scripts/official_eval.py report --config configs/frontier.yaml --round 3 > runs/frontier_official_report.log 2>&1

# (2) second model
CFG=configs/qwen3.yaml bash scripts/run_frontier.sh $EXTRA
python scripts/official_eval.py run    --config configs/qwen3.yaml --round 3 $EXTRA >> runs/qwen3_official.log 2>&1
python scripts/official_eval.py report --config configs/qwen3.yaml --round 3 > runs/qwen3_official_report.log 2>&1

cat runs/frontier_official_report.log runs/qwen3_official_report.log
