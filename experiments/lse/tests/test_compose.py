"""Compose every replication job against the real upstream Hydra config (no model, no GPU).

Skipped unless hydra is importable and the upstream checkout exists (setup.sh, or LSE_UPSTREAM).
Catches overrides that name keys absent from upstream configs, or values Hydra cannot parse.
"""
from pathlib import Path

import pytest
import yaml

hydra = pytest.importorskip("hydra")
from hydra import compose, initialize_config_dir  # noqa: E402

from lse_rsi.paths import upstream_root  # noqa: E402
from lse_rsi.replication import build_jobs  # noqa: E402

try:
    UP = upstream_root()
except FileNotFoundError:
    pytest.skip("upstream checkout not found", allow_module_level=True)

CFG = yaml.safe_load((Path(__file__).resolve().parent.parent / "configs" / "replication.yaml").read_text())
URL = "http://127.0.0.1:8000/v1"


def _compose(overrides):
    with initialize_config_dir(config_dir=str(UP / "configs"), version_base=None):
        return compose(config_name="base", overrides=overrides + ["run_name=t", "log_dir=/tmp/x"])


@pytest.mark.parametrize("job", build_jobs(CFG, model_url=URL) + build_jobs(CFG, model_url=URL, smoke=True),
                         ids=lambda j: j.run_name)
def test_job_composes_with_paper_settings(job):
    cfg = _compose(job.overrides)
    assert cfg.task.name == "bird" and cfg.task.db_id == job.db_id and cfg.seed == job.seed
    assert cfg.model.name == CFG["model"]["name"] and cfg.model.url == URL
    assert cfg.model.api_key is None
    assert cfg.tree.selection == "ucb" and cfg.tree.metric == "dev" and cfg.tree.enabled is True
    if job.run_name.startswith("smoke"):
        assert (cfg.n_round, cfg.n_sims, cfg.task.dev_size, cfg.test_n_eval) == (2, 2, 4, 2)
    else:
        assert (cfg.n_round, cfg.n_sims, cfg.task.dev_size, cfg.test_n_eval) == (25, 10, 50, 8)
        assert cfg.task.test_size == -1  # paper protocol: no separate test set (guide E.3)
    assert cfg.optimizer == ("gepa" if job.method == "gepa" else "lse")
    assert cfg.evolve_mode == ("textgrad" if job.method == "textgrad" else "self")


def test_upstream_defaults_still_differ_from_paper():
    """Guards guide E.3: if upstream defaults change, our overrides table must be re-checked."""
    cfg = _compose(["task=bird"])
    assert (cfg.n_round, cfg.n_sims, cfg.test_n_eval) == (5, 2, 1)
    assert cfg.tree.selection == "deepest" and cfg.tree.metric == "train"
    assert cfg.model.name == "Qwen/Qwen2.5-1.5B-Instruct"
