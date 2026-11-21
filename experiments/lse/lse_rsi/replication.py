"""Job list for stage-1 replication (guide E.4, R1-0 / R1-a / R1-b / R1-c)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from lse_rsi.paths import run_dir


@dataclass
class Job:
    method: str
    db_id: str
    seed: int
    run_name: str
    overrides: List[str] = field(default_factory=list)

    def directory(self, log_root: Path) -> Path:
        return run_dir(Path(log_root), self.method, self.run_name)


def _model_overrides(cfg: Dict[str, Any], model_url: Optional[str]) -> List[str]:
    out = [f"model.name={cfg['model']['name']}"]
    if model_url:
        out.append(f"model.url='{model_url}'")  # quoted: Hydra override grammar and ':' '/'
    return out


def build_jobs(cfg: Dict[str, Any], model_url: Optional[str] = None, smoke: bool = False,
               methods: Optional[List[str]] = None, databases: Optional[List[str]] = None,
               seeds: Optional[List[int]] = None) -> List[Job]:
    base = list(cfg["paper_overrides"]) + _model_overrides(cfg, model_url)
    if smoke:
        s = cfg["smoke"]
        name = f"smoke-lse-{s['database']}-s{s['seed']}"
        return [Job("lse", s["database"], int(s["seed"]), name,
                    base + list(s["overrides"]) + [f"task.db_id={s['database']}", f"seed={s['seed']}"])]
    jobs: List[Job] = []
    for method, extra in cfg["methods"].items():
        if methods and method not in methods:
            continue
        for db in cfg["databases"]:
            if databases and db not in databases:
                continue
            for seed in cfg["seeds"]:
                if seeds and int(seed) not in seeds:
                    continue
                name = f"r1-{method}-{db}-s{seed}"
                jobs.append(Job(method, db, int(seed), name,
                                base + list(extra or []) + [f"task.db_id={db}", f"seed={seed}"]))
    return jobs
