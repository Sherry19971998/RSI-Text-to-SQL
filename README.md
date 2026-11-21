# RSI Text-to-SQL — Phase 0 / Phase 1

Long-horizon rollout utility for recursive self-improving Text-to-SQL agents.
This code covers Phase 0 (infrastructure + noise floor) and Phase 1 (does rollout utility exist?).

## Layout

```
configs/default.yaml     Phase 1 settings (model, splits, rollout, LoRA, batch plan)
configs/phase0.yaml      Phase 0 overrides: 3 contrasting batches x 5 seeds
src/rsi/sandbox.py       Stage 2: static SQL check + read-only, authorizer-guarded, time-limited execution
src/rsi/prompts.py       schema serialization, prompts, SQL extraction
src/rsi/rollout.py       Stage 1: multi-turn generate -> execute -> repair episodes (vLLM)
src/rsi/train.py         short LoRA SFT on a rollout set (loss on assistant turns only)
src/rsi/batches.py       equally-correct candidate batches + covariates
src/rsi/analysis.py      paired bootstrap, random-effects ANOVA / ICC
scripts/                 one script per pipeline step (below)
```

Splits (`scripts/prepare_data.py`):
- `pool`: BIRD train questions for self-rollouts
- `util_val`: BIRD train questions on **databases disjoint from pool**, used to measure dP
- `test`: BIRD dev. Only for final reporting, never for selection or tuning.

## Setup (Linux + CUDA GPU)

```bash
python -m venv .venv && source .venv/bin/activate
pip install vllm            # pins a compatible torch
pip install -e ".[gpu,dev]"
pytest -q                   # CPU tests: sandbox, batches, stats
bash scripts/setup_bird_subset.sh   # small train dbs only (~5000 questions); low disk quota
# bash scripts/download_bird.sh     # full BIRD train + dev (~35 GB), for final test runs
```

## Run

```bash
# 0. data
python scripts/prepare_data.py --config configs/default.yaml \
  --train-json data/bird/train/train.json --train-db-root data/bird/train/dbs

# 1. theta_0 rollouts on pool (smoke test first)
python scripts/generate_pool.py --config configs/default.yaml --limit 50
python scripts/generate_pool.py --config configs/default.yaml

# 2. Phase 0 go/no-go
python scripts/build_batches.py --config configs/phase0.yaml
python scripts/train_batches.py --config configs/phase0.yaml          # shard over GPUs, see docstring
python scripts/evaluate.py      --config configs/phase0.yaml --repeat-base 2
python scripts/analyze.py       --config configs/phase0.yaml          # -> runs/phase0/report.md

# 3. Phase 1 (only after Phase 0 passes)
python scripts/build_batches.py --config configs/default.yaml
python scripts/train_batches.py --config configs/default.yaml
python scripts/evaluate.py      --config configs/default.yaml
python scripts/analyze.py       --config configs/default.yaml          # -> runs/phase1/report.md
```

All training and eval steps are resumable: finished adapters and eval files are skipped.

## Go / No-Go checks (Phase 0 report)

1. **Greedy re-run agreement** about 1.0. If it is lower, decoding is nondeterministic and adds eval noise.
2. **Seed noise** (within-batch SD of dP) should be clearly smaller than the gap between the `easy` / `hard` / `random` batches.
3. At least some runs have a paired-bootstrap CI that excludes 0, so a short LoRA update moves held-out accuracy at all.

If 2 or 3 fail, adjust the update (K, epochs, lr, LoRA rank) before running Phase 1.

Phase 1 passes when **ICC >= 0.3 and ANOVA p <= 0.05**: batch identity explains a substantial share of dP among equally-correct batches. Then check the confound table to confirm that dP is not just token count.

## Simplifications (for now)

- Schema is given in the prompt instead of an explicit "inspect schema" tool call.
- Correctness = BIRD execution accuracy (set equality). Test-suite accuracy (Spider) is not yet included.
- Phase 1 always trains from theta_0. `train_lora(init_adapter=...)` supports later RSI rounds.

## Phase 3: immediate vs. long-horizon utility

Round 1 is Phase 1: its adapters are θ₁ and its k = 4 sampled evaluations are U¹. Utility labels
use sampled pass rate (`evaluate.py --samples 4`), because greedy 0/1 accuracy cannot rank
individual sets (see `scripts/robustness.py`).

```bash
python scripts/evaluate.py --config configs/default.yaml --samples 4 --compile   # once: U¹ labels
bash scripts/run_phase3.sh --compile    # plan -> (gen -> train -> eval) per round -> report
```

`configs/phase3.yaml` sets the horizon H, the downstream selection rule every branch uses,
and how many sets are carried forward. Carried sets are drawn at random within each strategy,
never by U¹. `analyze_phase3.py` compares U¹ and Uᴴ rankings against a noise baseline: two
independent U¹ measurements, using different seeds and different question halves.

## Frontier experiment

Self-training raised per-sample accuracy but did not move the solving frontier: coverage fell
slightly after one round. This experiment tests whether choosing data that pushes the frontier
wins over several rounds. Four selection rules run from θ₀ for H = 3 rounds with 5 seeds:
`random`, `hard`, `frontier` (newly solved and rarely solved questions first), and `mix`. Each
round samples 8× per pool question and tops weak questions up to 32×. The rules share all
generated data and differ only in which K trajectories they train on.

```bash
CFG=configs/frontier_smoke.yaml bash scripts/run_frontier.sh --compile   # ~15 min end-to-end check
bash scripts/run_frontier.sh --compile                                     # full run, ~1-1.5 days
```

`analyze_frontier.py` reports pass rate and coverage curves per rule, and frontier movement on the
pool. It also reports paired rule differences per round with bootstrap CIs over seeds and questions.

Final test on BIRD dev (round-3 adapters + θ₀, k = 4):

```bash
bash scripts/setup_bird_dev.sh                       # download dev, build data/splits/test.jsonl
python scripts/frontier.py eval --config configs/frontier.yaml --round 3 --split test --compile
python scripts/analyze_frontier.py --config configs/frontier.yaml --split test   # -> runs/frontier/report_test.md
```

Official BIRD metric: greedy EX on all 1,534 dev questions, overall and by difficulty. Gold SQL
that still fails after a 10-minute timeout counts as wrong for every model:

```bash
python scripts/prepare_test.py --dev-json data/bird_dev/dev_20240627/dev.json \
  --dev-db-root data/bird_dev/dev_20240627/dev_databases --full --gold-timeout 600 --workers 32
python scripts/official_eval.py run    --config configs/frontier.yaml --round 3 --compile
python scripts/official_eval.py report --config configs/frontier.yaml --round 3   # -> runs/frontier/report_official_test_full.md
```

## Ablation of the frontier rule

`configs/ablation.yaml` removes one component per variant: one-per-question round-robin
(`frontier_no_cap`), the 32× top-up (`frontier_no_topup`), and pass-rate ordering (`dedup`, which
equals frontier without ordering in round 1). It runs 5 seeds per variant. The newly-solved tier
needs a previous round, so `frontier_no_newly` runs only in round 2, branching from frontier's
round-1 models. Scored with official greedy EX on BIRD dev:

```bash
bash scripts/run_ablation.sh --compile   # ~14 h; runs/ablation/report_official_test_full_r{1,2}.md
```

## Simplified rule and second model

The ablation showed that rarity ordering does the work, so `rare_first` (rarest questions first,
duplicates allowed, no newly-solved tier) is added to the main experiment and is the method in a
Qwen3-8B replication (`configs/qwen3.yaml`, non-thinking chat template via `chat_template_kwargs`).

```bash
python scripts/check_env.py --config configs/qwen3.yaml                  # label masking for Qwen3
CFG=configs/qwen3_smoke.yaml bash scripts/run_frontier.sh --compile       # ~20 min check
bash scripts/run_next.sh --compile                                         # both runs, ~1.7 days
```
