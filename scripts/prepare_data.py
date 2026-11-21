"""Build pool / util_val / test splits from BIRD, executing gold SQL once.

python scripts/prepare_data.py --config configs/default.yaml \
    --train-json data/bird/train/train.json --train-db-root data/bird/train/dbs

Questions whose database was not extracted (see setup_bird_subset.sh) are skipped.
--dev-json/--dev-db-root are optional: BIRD dev is only the final test set.
"""
import argparse
from collections import Counter
from pathlib import Path

from rsi.data import attach_gold, load_bird, split_by_db
from rsi.utils import load_config, write_json, write_jsonl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--train-json", required=True)
    ap.add_argument("--train-db-root", required=True)
    ap.add_argument("--dev-json")
    ap.add_argument("--dev-db-root")
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args()
    cfg = load_config(args.config)
    d = cfg["data"]
    out = Path(cfg["data_dir"])

    train_all = load_bird(args.train_json, args.train_db_root, "train")
    train_avail = [x for x in train_all if Path(x["db_path"]).exists()]
    print(f"train: {len(train_avail)}/{len(train_all)} questions have their database extracted")
    train, drop_train = attach_gold(train_avail, d["gold_timeout"], args.workers)
    dev, drop_dev = [], {}
    if args.dev_json:
        dev, drop_dev = attach_gold(load_bird(args.dev_json, args.dev_db_root, "dev"),
                                    d["gold_timeout"], args.workers)
    pool, val, val_dbs = split_by_db(train, d["util_val_size"], d["pool_size"], d["seed"])

    write_jsonl(out / "pool.jsonl", pool)
    write_jsonl(out / "util_val.jsonl", val)
    if dev:
        write_jsonl(out / "test.jsonl", dev)
    meta = {
        "n_pool": len(pool), "n_util_val": len(val), "n_test": len(dev),
        "util_val_dbs": val_dbs,
        "pool_dbs": sorted({x["db_id"] for x in pool}),
        "gold_dropped": {"train": drop_train, "dev": drop_dev},
        "test_difficulty": dict(Counter(x["difficulty"] for x in dev)),
    }
    write_json(out / "meta.json", meta)
    print({k: v for k, v in meta.items() if not k.endswith("_dbs")})


if __name__ == "__main__":
    main()
