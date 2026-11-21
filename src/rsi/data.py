"""BIRD loading and split construction.

Splits:
  pool      - BIRD train questions used to generate self-rollouts
  util_val  - BIRD train questions on databases disjoint from pool; used to measure dP
              (and later g_val / verifier labels)
  test      - BIRD dev; touched only for final reporting
"""
from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path

from .sandbox import execute_many


def load_bird(json_path, db_root, prefix: str) -> list[dict]:
    items = json.loads(Path(json_path).read_text())
    db_root = Path(db_root).resolve()
    out = []
    for i, x in enumerate(items):
        db_id = x["db_id"]
        out.append({
            "qid": f"{prefix}-{x.get('question_id', i)}",
            "db_id": db_id,
            "db_path": str(db_root / db_id / f"{db_id}.sqlite"),
            "question": x["question"],
            "evidence": x.get("evidence", ""),
            "gold_sql": x["SQL"],
            "difficulty": x.get("difficulty"),
        })
    return out


def attach_gold(items: list[dict], timeout: float, workers: int) -> tuple[list[dict], dict]:
    """Execute gold SQL once; keep items whose gold runs, store its result hash."""
    res = execute_many([(it["db_path"], it["gold_sql"]) for it in items],
                       timeout=timeout, workers=workers)
    kept, dropped = [], defaultdict(int)
    for it, r in zip(items, res):
        if not r["ok"]:
            dropped["error" if "timeout" not in r["error"] else "timeout"] += 1
        elif r["truncated"]:
            dropped["truncated"] += 1
        else:
            kept.append({**it, "gold_hash": r["hash"], "gold_n_rows": r["n_rows"]})
    return kept, dict(dropped)


def split_by_db(items: list[dict], util_val_size: int, pool_size: int, seed: int):
    """util_val takes whole databases until it has >= util_val_size questions, so its
    databases never appear in pool (mirrors BIRD's train/dev db disjointness)."""
    rng = random.Random(seed)
    by_db = defaultdict(list)
    for it in items:
        by_db[it["db_id"]].append(it)
    dbs = sorted(by_db)
    rng.shuffle(dbs)
    val_dbs, n = [], 0
    for db in dbs:
        if n >= util_val_size:
            break
        val_dbs.append(db)
        n += len(by_db[db])
    val = [it for db in val_dbs for it in by_db[db]]
    val_set = set(val_dbs)
    pool = [it for db in dbs if db not in val_set for it in by_db[db]]
    rng.shuffle(val)
    rng.shuffle(pool)
    return pool[:pool_size], val[:util_val_size], sorted(val_dbs)
