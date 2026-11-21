"""Run one upstream LSE / GEPA / TextGrad experiment and keep every logged metric as JSONL.

This mirrors upstream ``main.py`` exactly (same config, same simulator classes, same
log_dir handling). The only additions are:
  * every ``logger.log(...)`` call is also appended to ``<run_dir>/rsi_metrics.jsonl``
    (upstream otherwise only writes wandb's binary offline files);
  * ``<run_dir>/run_meta.json`` (overrides, upstream commit, timing) and
    ``<run_dir>/result.json`` (status and the simulator's return value).

Usage (inside the upstream venv, with PYTHONPATH pointing at experiments/lse):
    python -m lse_rsi.run --run-name NAME [--log-root DIR] -- task=bird task.db_id=financial ...
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List

from lse_rsi.paths import UPSTREAM_COMMIT, default_log_root, upstream_root

METRICS_FILE = "rsi_metrics.jsonl"
RESULT_FILE = "result.json"
META_FILE = "run_meta.json"


def _jsonable(v: Any) -> Any:
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if isinstance(v, (int, float, str, bool)) or v is None:
        return v
    try:
        return float(v)  # numpy scalars
    except (TypeError, ValueError):
        return str(v)


class TeeLogger:
    """Wraps a wandb run: forwards everything, and also appends log() calls to a JSONL file."""

    def __init__(self, inner: Any, path: Path):
        self._inner = inner
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, data: Dict[str, Any], step: Any = None, **kwargs: Any) -> Any:
        rec = {"step": step, "time": time.time()}
        rec.update({str(k): _jsonable(v) for k, v in dict(data).items()})
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return self._inner.log(data, step=step, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def _upstream_head(up: Path) -> str:
    try:
        return subprocess.run(["git", "-C", str(up), "rev-parse", "--short=7", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def _redact(overrides: List[str]) -> List[str]:
    return [o.split("=", 1)[0] + "=<redacted>" if o.split("=", 1)[0].endswith("api_key") else o
            for o in overrides]


def main(argv: List[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--" in argv:
        i = argv.index("--")
        own, overrides = argv[:i], argv[i + 1:]
    else:
        own, overrides = argv, []
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--run-name", required=True)
    p.add_argument("--log-root", default=str(default_log_root()))
    args = p.parse_args(own)

    if any(o.split("=", 1)[0].endswith("api_key") for o in overrides):
        print("Refusing model.api_key on the command line (upstream saves it to config.yaml); "
              "set OPENAI_API_KEY instead.", file=sys.stderr)
        return 2

    up = upstream_root()
    head = _upstream_head(up)
    if head not in ("unknown", UPSTREAM_COMMIT):
        print(f"Warning: upstream at {head}, expected {UPSTREAM_COMMIT}", file=sys.stderr)

    # Absolute data root: upstream's config default "data/bird" is resolved against the cwd.
    os.environ.setdefault("LSE_BIRD_DATA_ROOT", str(up / "data" / "bird"))
    os.environ.setdefault("WANDB_MODE", "offline")
    if str(up) not in sys.path:
        sys.path.insert(0, str(up))

    from hydra import compose, initialize_config_dir

    log_root = Path(args.log_root).resolve()
    with initialize_config_dir(config_dir=str(up / "configs"), version_base=None):
        cfg = compose(config_name="base",
                      overrides=overrides + [f"run_name={args.run_name}", f"log_dir={log_root}"])

    # --- identical to upstream main.py ---
    if cfg.debug:
        cfg.run_name = cfg.run_name + "_debug"
    task = cfg.task.name
    optimizer = getattr(cfg, "optimizer", "lse")
    if optimizer == "gepa":
        cfg.log_dir = f"{cfg.log_dir}/gepa/{cfg.task.name}"
    else:
        cfg.log_dir = f"{cfg.log_dir}/{cfg.task.name}"
    # -------------------------------------

    rdir = Path(cfg.log_dir) / cfg.run_name
    rdir.mkdir(parents=True, exist_ok=True)
    meta = {
        "run_name": cfg.run_name,
        "task": task,
        "optimizer": optimizer,
        "evolve_mode": str(getattr(cfg, "evolve_mode", "")),
        "overrides": _redact(overrides),
        "upstream_commit": head,
        "model_url_set": bool(getattr(cfg.model, "url", None)),
        "started": time.time(),
        "argv": _redact(sys.argv),
    }
    (rdir / META_FILE).write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    (rdir / RESULT_FILE).write_text(json.dumps({"status": "running"}))

    status, payload = "failed", {}
    try:
        if task != "bird":
            raise ValueError(f"Only task=bird is supported here, got {task}")
        if optimizer == "gepa":
            from lse.gepa.gepa_bird_simulator import GEPABirdSimulator
            sim = GEPABirdSimulator(cfg)
        else:
            from lse.simulators.bird_simulator import BirdSimulator
            sim = BirdSimulator(cfg)
        sim.logger = TeeLogger(sim.logger, rdir / METRICS_FILE)
        cb = getattr(sim, "callback", None)
        if cb is not None and hasattr(cb, "wandb_run"):
            cb.wandb_run = sim.logger  # GEPA's callback logs through its own reference
        results = sim.run_gepa() if optimizer == "gepa" else sim.run_self_evolve()
        print(f'Accuracy: {results["average_accuracy"]}')  # same line upstream prints
        payload = {"average_accuracy": [_jsonable(x) for x in results.get("average_accuracy", [])]}
        status = "done"
        try:
            sim.logger.finish()
        except Exception:
            pass
    except Exception:
        payload = {"error": traceback.format_exc()}
        print(payload["error"], file=sys.stderr)
    finally:
        meta["finished"] = time.time()
        (rdir / META_FILE).write_text(json.dumps(meta, indent=2, ensure_ascii=False))
        (rdir / RESULT_FILE).write_text(json.dumps({"status": status, **payload}, indent=2))
    return 0 if status == "done" else 1


if __name__ == "__main__":
    sys.exit(main())
