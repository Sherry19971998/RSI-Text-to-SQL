#!/usr/bin/env bash
# Frontier-rule ablation end to end (each stage resumable). Run inside tmux:
#   bash scripts/run_ablation.sh [--compile]
# Needs data/splits/test_full.jsonl (scripts/prepare_test.py --full). Reports:
#   runs/ablation/report_official_test_full_r1.md and _r2.md
set -euo pipefail
cd "$(dirname "$0")/.."
CFG=${CFG:-configs/ablation.yaml}
EXTRA="${1:-}"
for h in 1 2; do
  python scripts/frontier.py gen   --config $CFG --round "$h" $EXTRA >> runs/ab_gen.log 2>&1
  python scripts/frontier.py train --config $CFG --round "$h"        >> runs/ab_train.log 2>&1
done
for h in 1 2; do
  python scripts/official_eval.py run    --config $CFG --round "$h" $EXTRA >> runs/ab_eval.log 2>&1
  python scripts/official_eval.py report --config $CFG --round "$h" > "runs/ab_report_r$h.log" 2>&1
done
cat runs/ab_report_r1.log runs/ab_report_r2.log
