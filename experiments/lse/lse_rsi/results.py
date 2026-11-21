"""Read scores back from an upstream run directory (pure Python, no upstream imports).

Where each number lives (guide E.10):
  * lse / evolve_mode=self with tree.metric=dev: ``tree/tree.json`` stores, for every node, its
    holdout accuracy (``performance``). The root is the seed instruction (R1-0); the paper's
    reported number is the best holdout accuracy over the rounds (R1-a).
  * textgrad: the tree stores batch accuracy, not holdout accuracy, because TextGrad skips the
    round-start holdout evaluation; its holdout score is only logged, under
    ``textgrad/best_holdout_acc`` (captured in ``rsi_metrics.jsonl`` by lse_rsi.run).
  * gepa: ``result.json`` holds GEPA's best validation (D_pareto) accuracy per iteration.
  * any method with task.test_size > 0: ``test/selected`` = test accuracy of the round chosen
    by the best holdout accuracy (the number our main experiments report).
All accuracies are fractions in [0, 1].
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from lse_rsi.run import METRICS_FILE, RESULT_FILE


def _load_json(path: Path) -> Optional[Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def read_metrics(rdir: Path) -> List[Dict[str, Any]]:
    path = Path(rdir) / METRICS_FILE
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # tolerate a truncated last line from an interrupted run
    return out


def last_value(records: List[Dict[str, Any]], key: str) -> Optional[float]:
    for rec in reversed(records):
        v = rec.get(key)
        if isinstance(v, (int, float)):
            return float(v)
    return None


def tree_scores(rdir: Path) -> Dict[str, Optional[float]]:
    """Seed (root) and best holdout accuracy from tree.json; None when unavailable."""
    data = _load_json(Path(rdir) / "tree" / "tree.json")
    if not data:
        return {"seed": None, "best": None, "n_scored": 0}
    nodes = data.get("nodes", [])
    root_id = data.get("root_id")
    perf = {n["id"]: n.get("performance") for n in nodes}
    scored = [v for v in perf.values() if isinstance(v, (int, float))]
    return {
        "seed": perf.get(root_id) if isinstance(perf.get(root_id), (int, float)) else None,
        "best": max(scored) if scored else None,
        "n_scored": len(scored),
    }


def db_id_of(rdir: Path) -> Optional[str]:
    info = _load_json(Path(rdir) / "env" / "info.json") or {}
    return info.get("db_id") or info.get("val_db_id")


def summarize_run(rdir: Path, method: str) -> Dict[str, Any]:
    rdir = Path(rdir)
    res = _load_json(rdir / RESULT_FILE) or {"status": "missing"}
    metrics = read_metrics(rdir)
    row: Dict[str, Any] = {
        "run_dir": str(rdir),
        "method": method,
        "status": res.get("status", "missing"),
        "db_id": db_id_of(rdir),
        "seed_acc": None,
        "best_holdout": None,
        "test_selected": last_value(metrics, "test/selected"),
    }
    if method == "gepa":
        hist = [x for x in res.get("average_accuracy", []) if isinstance(x, (int, float))]
        row["best_holdout"] = hist[-1] if hist else last_value(metrics, "dev/best_acc")
    elif method == "textgrad":
        row["best_holdout"] = (last_value(metrics, "textgrad/best_holdout_acc")
                               if last_value(metrics, "textgrad/best_holdout_acc") is not None
                               else last_value(metrics, "dev/best_acc"))
    else:
        ts = tree_scores(rdir)
        row["seed_acc"] = ts["seed"]
        row["best_holdout"] = ts["best"]
        row["n_scored_nodes"] = ts["n_scored"]
        # Cross-check against the logged running maximum when both exist.
        logged = last_value(metrics, "dev/best_acc")
        if logged is not None and ts["best"] is not None and abs(logged - ts["best"]) > 1e-9:
            row["warning"] = f"tree best {ts['best']:.4f} != logged dev/best_acc {logged:.4f}"
    return row
