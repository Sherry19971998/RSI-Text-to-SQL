"""Readiness check for the OpenAI-compatible model server, and archiving of failed attempts."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional


def server_ready(url: str, timeout: float = 5.0) -> bool:
    """True if GET <url>/models answers 200 with a JSON model list."""
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/models", timeout=timeout) as r:
            return r.status == 200 and "data" in json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return False


def wait_for_server(url: str, max_wait: float = 1800.0, interval: float = 15.0,
                    log=print) -> bool:
    """Poll until the server is ready or max_wait seconds pass."""
    start = time.time()
    warned = False
    while True:
        if server_ready(url):
            if warned:
                log(f"    server back after {time.time() - start:.0f}s")
            return True
        if time.time() - start >= max_wait:
            return False
        if not warned:
            log(f"    waiting for model server at {url} ...")
            warned = True
        time.sleep(interval)


def archive_attempt(rdir: Path, stamp: Optional[str] = None) -> Optional[Path]:
    """Move an unfinished run directory aside (<name>.attempt-<stamp>) so a rerun starts clean.

    Upstream cannot resume a run, and our metrics file is append-only, so a rerun in the same
    directory would mix two attempts. The old attempt is kept for diagnosis, never deleted.
    """
    rdir = Path(rdir)
    if not rdir.exists():
        return None
    stamp = stamp or time.strftime("%Y%m%d-%H%M%S")
    dest = rdir.with_name(f"{rdir.name}.attempt-{stamp}")
    n = 1
    while dest.exists():
        dest = rdir.with_name(f"{rdir.name}.attempt-{stamp}-{n}")
        n += 1
    rdir.rename(dest)
    return dest
