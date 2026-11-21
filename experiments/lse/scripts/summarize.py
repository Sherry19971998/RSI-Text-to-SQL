"""Summarize stage-1 replication against LSE Table 1 (guide E.7).

Paper protocol: for each database, the best holdout accuracy over the rounds; then the average over
the 5 databases. We compute that average per seed (only for seeds with all databases finished),
then report the mean and range over seeds. Writes runs/replication_runs.csv and
runs/replication_summary.md.
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
from pathlib import Path
from typing import Dict, List, Optional

EXP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP))

import yaml  # noqa: E402

from lse_rsi.paths import default_log_root  # noqa: E402
from lse_rsi.replication import build_jobs  # noqa: E402
from lse_rsi.results import summarize_run  # noqa: E402


def pct(x: Optional[float]) -> str:
    return "—" if x is None else f"{100 * x:.1f}"


def seed_averages(rows: List[Dict], key: str, dbs: List[str]) -> Dict[int, float]:
    """Per seed, the average over databases; seeds missing any database are left out."""
    by_seed: Dict[int, Dict[str, float]] = {}
    for r in rows:
        if r["status"] == "done" and r.get(key) is not None:
            by_seed.setdefault(r["seed"], {})[r["db"]] = r[key]
    return {s: statistics.mean(v[d] for d in dbs) for s, v in by_seed.items() if all(d in v for d in dbs)}


def describe(vals: List[float]) -> str:
    if not vals:
        return "—"
    m = statistics.mean(vals)
    return f"{100 * m:.1f} ({100 * min(vals):.1f}–{100 * max(vals):.1f}, n={len(vals)})"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--config", default=str(EXP / "configs" / "replication.yaml"))
    p.add_argument("--log-root", default=str(default_log_root()))
    args = p.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text())
    log_root = Path(args.log_root).resolve()
    dbs = list(cfg["databases"])
    rows: List[Dict] = []
    for job in build_jobs(cfg):
        r = summarize_run(job.directory(log_root), job.method)
        r.update({"db": job.db_id, "seed": job.seed, "run_name": job.run_name})
        if r["db_id"] and r["db_id"] != job.db_id:
            r["warning"] = (r.get("warning", "") + f" db_id in run dir is {r['db_id']}").strip()
        rows.append(r)

    log_root.mkdir(parents=True, exist_ok=True)
    fields = ["run_name", "method", "db", "seed", "status", "seed_acc", "best_holdout",
              "test_selected", "warning", "run_dir"]
    with open(log_root / "replication_runs.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    targets = cfg["paper_targets"]
    lse_rows = [r for r in rows if r["method"] == "lse"]
    lines = ["# LSE stage-1 replication summary", "",
             f"Databases: {', '.join(dbs)}. Accuracy in %. Paper protocol: best holdout over rounds, "
             "5-database average per seed, then mean (range, n seeds).", "",
             "| Row | Paper | Ours (mean, range over seeds) |", "|---|---|---|",
             f"| R1-0 seed instruction (round 0 of lse runs) | {targets['seed']} | "
             f"{describe(list(seed_averages(lse_rows, 'seed_acc', dbs).values()))} |"]
    labels = {"lse": "R1-a untrained Qwen3-4B improver", "gepa": "R1-b GEPA", "textgrad": "R1-c TextGrad"}
    for method in cfg["methods"]:
        mrows = [r for r in rows if r["method"] == method]
        lines.append(f"| {labels.get(method, method)} | {targets.get(method, '—')} | "
                     f"{describe(list(seed_averages(mrows, 'best_holdout', dbs).values()))} |")

    lines += ["", "## Per database (mean over finished seeds)", "",
              "| Method | " + " | ".join(dbs) + " |", "|---|" + "---|" * len(dbs)]
    for method in ["seed"] + list(cfg["methods"]):
        key, src = ("seed_acc", "lse") if method == "seed" else ("best_holdout", method)
        cells = []
        for d in dbs:
            v = [r[key] for r in rows if r["method"] == src and r["db"] == d
                 and r["status"] == "done" and r.get(key) is not None]
            cells.append(pct(statistics.mean(v)) if v else "—")
        lines.append(f"| {method} | " + " | ".join(cells) + " |")

    n_done = sum(r["status"] == "done" for r in rows)
    warns = [r for r in rows if r.get("warning")]
    lines += ["", f"Runs finished: {n_done}/{len(rows)}."]
    if warns:
        lines += ["", "Warnings:"] + [f"- {r['run_name']}: {r['warning']}" for r in warns]
    lines += ["", "Notes: GEPA scores its holdout with 1 generation per question, LSE with 8 "
              "(guide E.3), so R1-b is not on the same footing as R1-a; compare each only with its "
              "own paper number. R1-0 and R1-a come from the same lse runs."]
    text = "\n".join(lines) + "\n"
    (log_root / "replication_summary.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
