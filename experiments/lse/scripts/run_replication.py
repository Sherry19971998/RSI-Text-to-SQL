"""Run stage-1 replication (guide E.4 R1) over methods x databases x seeds, one process per run.

Resumable: runs whose result.json says "done" are skipped. A run that is unfinished (failed or
interrupted) is rerun from scratch after its old directory is archived as <name>.attempt-<time>
(upstream cannot resume a run). Each run's stdout/stderr goes to <run_dir>/stdout.log.

When a model endpoint is used, each run first waits until the server answers; a failed run is
retried (default once) after the server is ready again. If the server stays down, the batch stops
instead of failing every remaining run.

    python scripts/run_replication.py --dry-run        # print the commands only
    python scripts/run_replication.py --smoke          # guide E.8 step 1
    python scripts/run_replication.py                  # all of configs/replication.yaml
    python scripts/run_replication.py --methods lse --databases financial --seeds 1
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP))

import yaml  # noqa: E402

from lse_rsi.health import archive_attempt, wait_for_server  # noqa: E402
from lse_rsi.paths import default_log_root  # noqa: E402
from lse_rsi.replication import build_jobs  # noqa: E402
from lse_rsi.run import RESULT_FILE  # noqa: E402


def run_status(rdir: Path) -> str:
    try:
        return json.loads((rdir / RESULT_FILE).read_text()).get("status", "unknown")
    except (FileNotFoundError, json.JSONDecodeError):
        return "missing"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--config", default=str(EXP / "configs" / "replication.yaml"))
    p.add_argument("--log-root", default=str(default_log_root()))
    p.add_argument("--smoke", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--methods", nargs="*")
    p.add_argument("--databases", nargs="*")
    p.add_argument("--seeds", nargs="*", type=int)
    p.add_argument("--force", action="store_true", help="re-run even if result.json says done")
    p.add_argument("--retries", type=int, default=1, help="extra attempts for a failed run")
    p.add_argument("--server-wait", type=float, default=1800.0,
                   help="seconds to wait for the model server before giving up on the batch")
    args = p.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text())
    url = (os.environ.get(cfg["model"]["url_env"]) or "").strip() or None
    jobs = build_jobs(cfg, model_url=url, smoke=args.smoke, methods=args.methods,
                      databases=args.databases, seeds=args.seeds)
    log_root = Path(args.log_root).resolve()
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{EXP}{os.pathsep}{env.get('PYTHONPATH', '')}"
    print(f"{len(jobs)} runs; model via {'endpoint ' + url if url else 'local vLLM'}; log root {log_root}")

    failed = []
    for k, job in enumerate(jobs, 1):
        rdir = job.directory(log_root)
        cmd = [sys.executable, "-m", "lse_rsi.run", "--run-name", job.run_name,
               "--log-root", str(log_root), "--", *job.overrides]
        if args.dry_run:
            print(" ".join(cmd))
            continue
        if not args.force and run_status(rdir) == "done":
            print(f"[{k}/{len(jobs)}] skip (done) {job.run_name}")
            continue
        for attempt in range(args.retries + 1):
            if url and not wait_for_server(url, max_wait=args.server_wait):
                print(f"Model server at {url} not ready after {args.server_wait:.0f}s; stopping the batch.")
                return 2
            old = archive_attempt(rdir)  # never mix two attempts in one directory
            if old:
                print(f"    archived previous attempt -> {old.name}")
            rdir.mkdir(parents=True, exist_ok=True)
            t0 = time.time()
            print(f"[{k}/{len(jobs)}] run {job.run_name} (attempt {attempt + 1})", flush=True)
            with open(rdir / "stdout.log", "a", encoding="utf-8") as out:
                rc = subprocess.run(cmd, cwd=str(EXP), env=env, stdout=out,
                                    stderr=subprocess.STDOUT).returncode
            print(f"    exit {rc} after {time.time() - t0:.0f}s", flush=True)
            if rc == 0:
                break
        else:
            failed.append(job.run_name)
    if failed:
        print(f"{len(failed)} run(s) failed after retries: {', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
