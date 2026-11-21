#!/usr/bin/env bash
# Whole frontier experiment, round by round (each stage resumable). Run inside tmux:
#   bash scripts/run_frontier.sh [--compile]
# Logs: runs/<config>_*.log; report: <run_dir>/report.md. Smoke test: CFG=configs/frontier_smoke.yaml bash ...
set -euo pipefail
cd "$(dirname "$0")/.."
CFG=${CFG:-configs/frontier.yaml}
EXTRA="${1:-}"
TAG=$(basename "$CFG" .yaml)   # separate logs per experiment: runs/<config>_gen.log, ...
H=$(python -c "from rsi.utils import load_config; print(load_config('$CFG')['frontier']['horizon'])")
for h in $(seq 1 "$H"); do
  python scripts/frontier.py gen   --config $CFG --round "$h" $EXTRA >> runs/${TAG}_gen.log 2>&1
  python scripts/frontier.py train --config $CFG --round "$h"        >> runs/${TAG}_train.log 2>&1
  python scripts/frontier.py eval  --config $CFG --round "$h" $EXTRA >> runs/${TAG}_eval.log 2>&1
  python scripts/analyze_frontier.py --config $CFG > runs/${TAG}_report.log 2>&1 || true   # report after every round
done
tail -n 40 runs/${TAG}_report.log
