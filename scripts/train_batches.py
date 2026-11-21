"""Train one LoRA adapter per (batch, seed), starting from theta_0. Resumable; shard
across GPUs by launching one process per GPU:

for i in 0 1 2 3; do
  CUDA_VISIBLE_DEVICES=$i python scripts/train_batches.py --config configs/default.yaml \
      --shard $i --num-shards 4 &
done; wait
"""
import argparse
from pathlib import Path

from rsi.train import train_lora
from rsi.utils import load_config, read_json, read_jsonl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--num-shards", type=int, default=1)
    args = ap.parse_args()
    cfg = load_config(args.config)
    run_dir = Path(cfg["run_dir"])
    batches = read_json(run_dir / "batches.json")
    trajs = {t["traj_id"]: t for t in read_jsonl(cfg["pool_rollouts"])}

    jobs = [(b, s) for b in batches for s in cfg["batches"]["seeds"]]
    for b, seed in jobs[args.shard::args.num_shards]:
        out = run_dir / "adapters" / f"{b['batch_id']}__s{seed}"
        if (out / "adapter_config.json").exists():
            print(f"skip {out.name}")
            continue
        convs = [trajs[i]["messages"] for i in b["traj_ids"]]
        meta = train_lora(cfg["model"], convs, out, seed, cfg["train"])
        print(f"done {out.name}: {meta}")


if __name__ == "__main__":
    main()
