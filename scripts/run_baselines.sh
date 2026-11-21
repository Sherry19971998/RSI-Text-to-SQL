#!/usr/bin/env bash
# Literature baselines (informative, cartography) and restart-from-base controls for Qwen2.5-Coder-7B,
# then re-run the official BIRD dev evaluation of ALL round-3 adapters in one session (earlier
# results kept as eval_greedy_prev), so every rule is compared within a single evaluation run.
# Run inside tmux:   bash scripts/run_baselines.sh --compile
set -euo pipefail
cd "$(dirname "$0")/.."
EXTRA="${1:-}"
CFG=configs/baselines.yaml bash scripts/run_frontier.sh $EXTRA
if [ -d runs/frontier/eval_greedy ] && [ ! -d runs/frontier/eval_greedy_prev ]; then
  mv runs/frontier/eval_greedy runs/frontier/eval_greedy_prev
fi
python scripts/official_eval.py run    --config configs/baselines.yaml --round 3 $EXTRA >> runs/baselines_official.log 2>&1
python scripts/official_eval.py report --config configs/baselines.yaml --round 3 > runs/baselines_official_report.log 2>&1
cat runs/baselines_official_report.log
