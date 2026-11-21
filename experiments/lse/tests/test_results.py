"""Parsing of upstream run directories. Fixtures are tiny hand-made files that only exercise
the parsing logic; they are not experiment data."""
import json
from pathlib import Path

from lse_rsi.results import read_metrics, summarize_run, tree_scores
from lse_rsi.run import METRICS_FILE, RESULT_FILE, TeeLogger


def _write_tree(rdir: Path, perfs):
    nodes = [{"id": i, "parent_id": (None if i == 0 else i - 1), "performance": p}
             for i, p in enumerate(perfs)]
    (rdir / "tree").mkdir(parents=True)
    (rdir / "tree" / "tree.json").write_text(json.dumps({"root_id": 0, "nodes": nodes}))


def _write(rdir: Path, name: str, obj):
    rdir.mkdir(parents=True, exist_ok=True)
    (rdir / name).write_text(json.dumps(obj))


def _metrics(rdir: Path, recs):
    rdir.mkdir(parents=True, exist_ok=True)
    (rdir / METRICS_FILE).write_text("\n".join(json.dumps(r) for r in recs) + "\n")


def test_tree_scores_seed_best_and_unscored_last_node(tmp_path):
    # last node is never evaluated (created in the final round) -> performance None
    _write_tree(tmp_path, [0.5, 0.6, 0.55, None])
    ts = tree_scores(tmp_path)
    assert ts == {"seed": 0.5, "best": 0.6, "n_scored": 3}


def test_tree_scores_missing(tmp_path):
    assert tree_scores(tmp_path) == {"seed": None, "best": None, "n_scored": 0}


def test_summarize_lse_crosscheck(tmp_path):
    _write_tree(tmp_path, [0.5, 0.62, None])
    _write(tmp_path, RESULT_FILE, {"status": "done", "average_accuracy": [0.4, 0.7]})
    _write(tmp_path / "env", "info.json", {"db_id": "financial"})
    _metrics(tmp_path, [{"step": 0, "dev/best_acc": 0.5}, {"step": 1, "dev/best_acc": 0.62}])
    row = summarize_run(tmp_path, "lse")
    assert row["status"] == "done" and row["db_id"] == "financial"
    assert row["seed_acc"] == 0.5 and row["best_holdout"] == 0.62
    assert "warning" not in row
    # batch accuracies in result.json must NOT be mistaken for holdout scores
    assert row["best_holdout"] != 0.7


def test_summarize_lse_flags_mismatch(tmp_path):
    _write_tree(tmp_path, [0.5, 0.62])
    _write(tmp_path, RESULT_FILE, {"status": "done"})
    _metrics(tmp_path, [{"step": 1, "dev/best_acc": 0.64}])
    assert "warning" in summarize_run(tmp_path, "lse")


def test_summarize_textgrad_uses_logged_holdout(tmp_path):
    _write_tree(tmp_path, [0.9, 0.95])  # batch accuracies: must be ignored for textgrad
    _write(tmp_path, RESULT_FILE, {"status": "done"})
    _metrics(tmp_path, [{"step": 0, "textgrad/best_holdout_acc": 0.58, "dev/best_acc": 0.58},
                        {"step": 1, "textgrad/best_holdout_acc": 0.61, "test/selected": 0.6}])
    row = summarize_run(tmp_path, "textgrad")
    assert row["best_holdout"] == 0.61 and row["seed_acc"] is None and row["test_selected"] == 0.6


def test_summarize_gepa_uses_best_val_history(tmp_path):
    _write(tmp_path, RESULT_FILE, {"status": "done", "average_accuracy": [0.55, 0.6, 0.63]})
    _write(tmp_path / "env", "info.json", {"val_db_id": "toxicology"})
    row = summarize_run(tmp_path, "gepa")
    assert row["best_holdout"] == 0.63 and row["db_id"] == "toxicology"


def test_summarize_missing_run(tmp_path):
    row = summarize_run(tmp_path / "nope", "lse")
    assert row["status"] == "missing" and row["best_holdout"] is None


def test_read_metrics_tolerates_truncated_line(tmp_path):
    (tmp_path / METRICS_FILE).write_text('{"step": 0, "a": 1}\n{"step": 1, "a"')
    assert read_metrics(tmp_path) == [{"step": 0, "a": 1}]


class _FakeRun:
    def __init__(self):
        self.calls = []
        self.name = "fake"

    def log(self, data, step=None):
        self.calls.append((data, step))


def test_tee_logger_forwards_and_records(tmp_path):
    inner = _FakeRun()
    tee = TeeLogger(inner, tmp_path / "m.jsonl")
    tee.log({"dev/avg_acc": 0.5, "x": float("nan")}, step=3)
    assert len(inner.calls) == 1
    data, step = inner.calls[0]
    assert step == 3 and data["dev/avg_acc"] == 0.5 and data["x"] != data["x"]  # NaN forwarded unchanged
    rec = json.loads((tmp_path / "m.jsonl").read_text().strip())
    assert rec["step"] == 3 and rec["dev/avg_acc"] == 0.5 and rec["x"] is None
    assert tee.name == "fake"  # attribute passthrough
