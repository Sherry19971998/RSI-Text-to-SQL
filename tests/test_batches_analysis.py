import random

import numpy as np
import pytest

from rsi.analysis import one_way_anova, paired_bootstrap
from rsi.batches import build_batches
from rsi.data import split_by_db
from rsi.utils import load_config


def fake_trajs(n_q=300, n_s=8, seed=0):
    rng = random.Random(seed)
    out = []
    for q in range(n_q):
        p = rng.random()
        for k in range(n_s):
            turns = rng.choice([1, 1, 1, 2, 3])
            out.append({"traj_id": f"q{q}#{k}", "qid": f"q{q}", "db_id": f"db{q % 20}",
                        "correct": rng.random() < p, "safe_all": True, "n_turns": turns,
                        "n_failed_exec": turns - 1, "n_empty": 0, "recovered": turns > 1,
                        "schema_ok_all": True, "n_out_tokens": rng.randint(50, 500)})
    return out


PLAN = {"random": 2, "easy": 1, "hard": 1, "repair_rich": 1, "no_repair": 1, "db_diverse": 1,
        "db_narrow": 1, "dedup": 1, "dup": 1, "short": 1, "long": 1}


def test_batches_equal_size_correct_and_deterministic():
    trajs = fake_trajs()
    by_id = {t["traj_id"]: t for t in trajs}
    b1 = build_batches(trajs, PLAN, K=200, seed=0)
    b2 = build_batches(trajs, PLAN, K=200, seed=0)
    assert [b["traj_ids"] for b in b1] == [b["traj_ids"] for b in b2]
    for b in b1:
        assert len(b["traj_ids"]) == 200 == len(set(b["traj_ids"]))
        assert all(by_id[i]["correct"] for i in b["traj_ids"])
    cov = {b["strategy"]: b["covariates"] for b in b1}
    assert cov["easy"]["mean_pass_rate"] > cov["hard"]["mean_pass_rate"]
    # Easy questions contribute more correct trajectories; "hard" must still be clearly
    # harder than random (terciles over questions, not trajectories).
    rand = np.mean([b["covariates"]["mean_pass_rate"] for b in b1 if b["strategy"] == "random"])
    assert cov["hard"]["mean_pass_rate"] < rand - 0.2
    assert cov["repair_rich"]["repair_frac"] > cov["no_repair"]["repair_frac"]
    assert cov["db_diverse"]["n_dbs"] > cov["db_narrow"]["n_dbs"]
    assert cov["dedup"]["n_unique_q"] > cov["dup"]["n_unique_q"]
    assert cov["long"]["mean_out_tokens"] > cov["short"]["mean_out_tokens"]


def test_unknown_strategy_rejected():
    with pytest.raises(ValueError):
        build_batches(fake_trajs(50), {"nope": 1}, K=10)


def test_anova_detects_batch_effect_and_not_noise():
    rng = np.random.default_rng(0)
    effect = [rng.normal(m, 0.002, 3) for m in np.linspace(-0.02, 0.02, 10)]
    a = one_way_anova(effect)
    assert a["icc"] > 0.9 and a["p"] < 1e-6
    noise = [rng.normal(0, 0.01, 3) for _ in range(10)]
    assert one_way_anova(noise)["icc"] < 0.5


def test_paired_bootstrap():
    a = np.array([1] * 60 + [0] * 40)
    b = np.array([1] * 50 + [0] * 50)
    d, lo, hi = paired_bootstrap(a, b)
    assert d == pytest.approx(0.1) and lo > 0 and hi < 0.2


def test_split_by_db_disjoint():
    items = [{"qid": str(i), "db_id": f"db{i % 15}"} for i in range(1500)]
    pool, val, val_dbs = split_by_db(items, util_val_size=300, pool_size=800, seed=0)
    assert len(val) == 300 and len(pool) == 800
    assert not ({x["db_id"] for x in pool} & {x["db_id"] for x in val})


def test_configs_load():
    p0 = load_config("configs/phase0.yaml")
    assert p0["batches"]["plan"] == {"random": 1, "easy": 1, "hard": 1}
    assert p0["batches"]["K"] == 400 and p0["run_dir"] == "runs/phase0"


def _gains(true, noise, n_seeds=3, n_q=400, seed=0):
    rng = np.random.default_rng(seed)
    return true[:, None, None] + rng.normal(0, noise, (len(true), n_seeds, n_q))


def test_reversal_test_same_vs_independent_utilities():
    from rsi.analysis import reversal_test
    rng = np.random.default_rng(1)
    t1 = rng.normal(0, 0.01, 24)
    same = reversal_test(_gains(t1, 0.05, seed=2), _gains(t1, 0.05, seed=3), n_iter=200)
    assert same["disattenuated"] > 0.8 and same["flip_rate_cross"] < 0.35
    indep = reversal_test(_gains(t1, 0.05, seed=2), _gains(rng.normal(0, 0.01, 24), 0.05, seed=3), n_iter=200)
    assert indep["disattenuated"] < 0.5 and indep["p_cross_below_ceiling"] > 0.8


def test_catchup_test_removes_regression_to_mean():
    from rsi.analysis import catchup_test
    rng = np.random.default_rng(0)
    n_sets, n_seeds, n_q = 24, 3, 400
    t1 = rng.normal(0.02, 0.005, n_sets)
    p1_noise = rng.normal(0, 0.08, (n_sets, n_seeds, n_q))          # shared measurement noise in P(theta_1)
    U1 = t1[:, None, None] + p1_noise + rng.normal(0, 0.05, (n_sets, n_seeds, n_q))
    LATER = 0.01 - p1_noise + rng.normal(0, 0.05, (n_sets, n_seeds, n_q))  # no true catch-up
    r = catchup_test(U1, LATER, n_iter=200)
    assert r["naive"] < -0.3 and abs(r["cross"]) < 0.15
