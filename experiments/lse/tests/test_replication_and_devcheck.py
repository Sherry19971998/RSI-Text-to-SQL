import json
from pathlib import Path

import yaml

from check_dev_version import compare, load
from lse_rsi.replication import build_jobs

CFG = yaml.safe_load((Path(__file__).resolve().parent.parent / "configs" / "replication.yaml").read_text())


def test_full_job_grid():
    jobs = build_jobs(CFG)
    assert len(jobs) == len(CFG["methods"]) * len(CFG["databases"]) * len(CFG["seeds"])
    names = [j.run_name for j in jobs]
    assert len(set(names)) == len(names)


def test_paper_overrides_present_and_db_seed_last():
    j = [x for x in build_jobs(CFG) if x.method == "gepa"][0]
    for o in ["n_round=25", "n_sims=10", "task.dev_size=50", "test_n_eval=8",
              "tree.selection=ucb", "tree.metric=dev", "optimizer=gepa"]:
        assert o in j.overrides
    assert j.overrides[-2].startswith("task.db_id=") and j.overrides[-1].startswith("seed=")
    assert not any("api_key" in o for o in j.overrides)


def test_model_url_quoted_and_optional():
    j = build_jobs(CFG, model_url="http://h:8000/v1")[0]
    assert "model.url='http://h:8000/v1'" in j.overrides
    assert not any(o.startswith("model.url") for o in build_jobs(CFG)[0].overrides)


def test_run_dirs_follow_upstream_layout(tmp_path):
    j_lse = build_jobs(CFG, methods=["lse"])[0]
    j_gepa = build_jobs(CFG, methods=["gepa"])[0]
    assert j_lse.directory(tmp_path) == tmp_path / "bird" / j_lse.run_name
    assert j_gepa.directory(tmp_path) == tmp_path / "gepa" / "bird" / j_gepa.run_name


def test_smoke_and_filters():
    s = build_jobs(CFG, smoke=True)
    assert len(s) == 1 and "n_round=2" in s[0].overrides
    # smoke overrides must come after the paper ones so they win
    assert s[0].overrides.index("n_round=2") > s[0].overrides.index("n_round=25")
    f = build_jobs(CFG, methods=["lse"], databases=["financial"], seeds=[2])
    assert [j.run_name for j in f] == ["r1-lse-financial-s2"]


def test_dev_compare(tmp_path):
    a = [{"question_id": 0, "db_id": "x", "question": "q", "evidence": "", "SQL": "SELECT  1"},
         {"question_id": 1, "db_id": "x", "question": "q2", "evidence": "", "SQL": "SELECT 2"}]
    b = [{"question_id": 0, "db_id": "x", "question": "q", "evidence": "", "SQL": "SELECT 1"},
         {"question_id": 1, "db_id": "x", "question": "q2", "evidence": "", "SQL": "SELECT 3"},
         {"question_id": 2, "db_id": "y", "question": "q3", "evidence": "", "SQL": "SELECT 4"}]
    (tmp_path / "a.json").write_text(json.dumps(a))
    (tmp_path / "b.json").write_text(json.dumps(b))
    rep = compare(load(tmp_path / "a.json"), load(tmp_path / "b.json"))
    assert rep["only_in_b"] == [2] and rep["only_in_a"] == []
    assert rep["n_questions_differing"] == 1  # whitespace-only difference in q0 is ignored
    assert rep["field_diff_counts"]["SQL"] == 1
