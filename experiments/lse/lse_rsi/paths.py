"""Locations of the experiment folder, the upstream checkout, and run outputs."""
from __future__ import annotations

import os
from pathlib import Path

EXP_ROOT = Path(__file__).resolve().parent.parent
UPSTREAM_COMMIT = "9eb5eac"


def upstream_root() -> Path:
    """Upstream checkout; override with LSE_UPSTREAM for a checkout elsewhere."""
    raw = (os.environ.get("LSE_UPSTREAM") or "").strip()
    root = Path(raw).expanduser().resolve() if raw else EXP_ROOT / "third_party" / "learning-to-self-evolve"
    if not (root / "main.py").exists():
        raise FileNotFoundError(f"Upstream LSE not found at {root}; run setup.sh first.")
    return root


def default_log_root() -> Path:
    return EXP_ROOT / "runs"


def run_dir(log_root: Path, method: str, run_name: str, task: str = "bird") -> Path:
    """Directory upstream writes a run into (mirrors upstream main.py's log_dir handling)."""
    base = Path(log_root) / "gepa" / task if method == "gepa" else Path(log_root) / task
    return base / run_name
