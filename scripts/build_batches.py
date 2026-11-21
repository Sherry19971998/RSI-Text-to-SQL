"""Construct candidate batches B_1..B_M from theta_0 pool rollouts.

python scripts/build_batches.py --config configs/phase0.yaml
"""
import argparse
from pathlib import Path

from rsi.batches import build_batches
from rsi.utils import load_config, read_jsonl, write_json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    args = ap.parse_args()
    cfg = load_config(args.config)
    b = cfg["batches"]
    trajs = read_jsonl(cfg["pool_rollouts"])
    batches = build_batches(trajs, b["plan"], b["K"], seed=cfg["data"]["seed"])
    out = Path(cfg["run_dir"]) / "batches.json"
    write_json(out, batches)
    print(f"wrote {len(batches)} batches -> {out}")
    for x in batches:
        c = x["covariates"]
        print(f"  {x['batch_id']:<14} pref={x['preferred_frac']:.2f} q={c['n_unique_q']:<4} "
              f"dbs={c['n_dbs']:<3} pass={c['mean_pass_rate']:.2f} repair={c['repair_frac']:.2f} "
              f"tok={c['mean_out_tokens']:.0f}")


if __name__ == "__main__":
    main()
