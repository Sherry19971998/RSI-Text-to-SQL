#!/usr/bin/env bash
# Whole Phase 3, stage by stage (each stage resumable). Run inside tmux:
#   bash scripts/run_phase3.sh [--compile]
# Logs: runs/p3_*.log; report: runs/phase3/report.md
set -euo pipefail
cd "$(dirname "$0")/.."
CFG=configs/phase3.yaml
EXTRA="${1:-}"

[ -f runs/phase3/plan.json ] || python scripts/phase3.py plan --config $CFG | tee runs/p3_plan.log
H=$(python -c "import json; print(json.load(open('runs/phase3/plan.json'))['horizon'])")
for h in $(seq 2 "$H"); do
  python scripts/phase3.py gen   --config $CFG --round "$h" $EXTRA >> runs/p3_gen.log 2>&1
  python scripts/phase3.py train --config $CFG --round "$h"        >> runs/p3_train.log 2>&1
  python scripts/phase3.py eval  --config $CFG --round "$h" $EXTRA >> runs/p3_eval.log 2>&1
done
python scripts/analyze_phase3.py --config $CFG > runs/p3_report.log 2>&1
tail -n 25 runs/p3_report.log
