"""Build a test split from BIRD dev (gold SQL executed once). Leaves the other splits alone.

Default: data/splits/test.jsonl, dropping questions whose gold SQL fails within the timeout.
--full: data/splits/test_full.jsonl with every question kept (official BIRD protocol); a gold
that still fails gets gold_hash = None, so every model is scored wrong on it.

python scripts/prepare_test.py --dev-json data/bird_dev/dev_20240627/dev.json \
    --dev-db-root data/bird_dev/dev_20240627/dev_databases [--full --gold-timeout 600]
"""
import argparse
from collections import Counter
from pathlib import Path

from rsi.data import attach_gold, load_bird
from rsi.sandbox import execute_many
from rsi.utils import load_config, write_jsonl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--dev-json", required=True)
    ap.add_argument("--dev-db-root", required=True)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--full", action="store_true", help="keep all questions -> test_full.jsonl")
    ap.add_argument("--gold-timeout", type=float, default=None, help="default: data.gold_timeout")
    ap.add_argument("--max-rows", type=int, default=2_000_000, help="row cap for gold results (--full)")
    args = ap.parse_args()
    cfg = load_config(args.config)
    timeout = args.gold_timeout or cfg["data"]["gold_timeout"]
    items = load_bird(args.dev_json, Path(args.dev_db_root).resolve(), "dev")
    missing = sorted({x["db_id"] for x in items if not Path(x["db_path"]).exists()})
    if missing:
        raise SystemExit(f"databases not found under {args.dev_db_root}: {missing}")

    if not args.full:
        test, dropped = attach_gold(items, timeout, args.workers)
        write_jsonl(Path(cfg["data_dir"]) / "test.jsonl", test)
        print(f"test: {len(test)}/{len(items)} questions (gold dropped: {dropped}); "
              f"difficulty: {dict(Counter(x['difficulty'] for x in test))}")
        return

    res = execute_many([(x["db_path"], x["gold_sql"]) for x in items], timeout=timeout,
                       workers=args.workers, max_rows=args.max_rows)
    out, failed = [], Counter()
    for x, r in zip(items, res):
        ok = r["ok"] and not r["truncated"]
        if not ok:
            failed["timeout" if "timeout" in (r["error"] or "") else "truncated" if r["truncated"] else "error"] += 1
        out.append({**x, "gold_hash": r["hash"] if ok else None, "gold_n_rows": r["n_rows"], "gold_failed": not ok})
    write_jsonl(Path(cfg["data_dir"]) / "test_full.jsonl", out)
    print(f"test_full: {len(out)} questions, gold still failing: {dict(failed)} (scored wrong for every model); "
          f"difficulty: {dict(Counter(x['difficulty'] for x in out))}")


if __name__ == "__main__":
    main()
