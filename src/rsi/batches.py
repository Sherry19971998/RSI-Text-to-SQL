"""Phase 1 candidate-batch construction.

Every batch holds exactly K execution-correct, safe trajectories, so batches are
"equally correct" by construction. Structured strategies push batches to different
corners of trajectory space (difficulty, repairs, db coverage, duplication, length);
`random` batches are the reference distribution. Covariates are recorded per batch
so the analysis can check that utility is not just a size/length artifact.
"""
from __future__ import annotations

import random
from collections import defaultdict

import numpy as np


def question_pass_rates(trajs) -> dict:
    tot, cor = defaultdict(int), defaultdict(int)
    for t in trajs:
        tot[t["qid"]] += 1
        cor[t["qid"]] += int(t["correct"])
    return {q: cor[q] / tot[q] for q in tot}


def _prefer(preferred, rest, K, rng):
    """Sample K ids, preferring `preferred`; fill from `rest` if short."""
    preferred = list(preferred)
    rng.shuffle(preferred)
    take = preferred[:K]
    if len(take) < K:
        taken = set(take)
        pool = [t for t in rest if t not in taken]
        rng.shuffle(pool)
        take += pool[:K - len(take)]
    return take, min(len(preferred), K) / K


def _terciles(values):
    return np.quantile(values, [1 / 3, 2 / 3])


def _by_quantile(elig, key, side, K, rng, unit=None):
    """Prefer trajectories in the low/high tercile of key(t). With `unit` (e.g. qid), the
    terciles are computed over units, not trajectories: easy questions contribute up to
    n_samples correct trajectories each, which would otherwise swamp the low tercile."""
    vals = [key(t) for t in elig]
    if unit is None:
        lo, hi = _terciles(vals)
    else:
        lo, hi = _terciles(list({unit(t): v for t, v in zip(elig, vals)}.values()))
    pref = [t["traj_id"] for t, v in zip(elig, vals) if (v <= lo if side == "low" else v >= hi)]
    return _prefer(pref, [t["traj_id"] for t in elig], K, rng)


def _db_diverse(elig, K, rng):
    by_db = defaultdict(list)
    for t in elig:
        by_db[t["db_id"]].append(t["traj_id"])
    for v in by_db.values():
        rng.shuffle(v)
    dbs = list(by_db)
    rng.shuffle(dbs)
    out, i = [], 0
    while len(out) < K and any(by_db.values()):
        db = dbs[i % len(dbs)]
        if by_db[db]:
            out.append(by_db[db].pop())
        i += 1
    return out, 1.0


def _db_narrow(elig, K, rng):
    by_db = defaultdict(list)
    for t in elig:
        by_db[t["db_id"]].append(t["traj_id"])
    dbs = list(by_db)
    rng.shuffle(dbs)
    chosen = []
    for db in dbs:
        chosen += by_db[db]
        if len(chosen) >= K:
            break
    return _prefer(chosen, [t["traj_id"] for t in elig], K, rng)


def _dedup(elig, K, rng):
    by_q = defaultdict(list)
    for t in elig:
        by_q[t["qid"]].append(t["traj_id"])
    qs = list(by_q)
    rng.shuffle(qs)
    pref = [rng.choice(by_q[q]) for q in qs[:K]]
    return _prefer(pref, [t["traj_id"] for t in elig], K, rng)


def _dup(elig, K, rng):
    by_q = defaultdict(list)
    for t in elig:
        by_q[t["qid"]].append(t["traj_id"])
    qs = [q for q in by_q if len(by_q[q]) >= 4] or list(by_q)
    rng.shuffle(qs)
    out = []
    for q in qs:
        out += by_q[q]
        if len(out) >= K:
            break
    return out[:K], min(len(out), K) / K


def build_batches(trajs, plan: dict, K: int, seed: int = 0) -> list[dict]:
    rates = question_pass_rates(trajs)
    elig = [t for t in trajs if t["correct"] and t["safe_all"]]
    if len(elig) < K:
        raise ValueError(f"only {len(elig)} eligible trajectories < K={K}")
    all_ids = [t["traj_id"] for t in elig]
    by_id = {t["traj_id"]: t for t in elig}

    strategies = {
        "random": lambda rng: (rng.sample(all_ids, K), 1.0),
        "easy": lambda rng: _by_quantile(elig, lambda t: rates[t["qid"]], "high", K, rng, unit=lambda t: t["qid"]),
        "hard": lambda rng: _by_quantile(elig, lambda t: rates[t["qid"]], "low", K, rng, unit=lambda t: t["qid"]),
        "repair_rich": lambda rng: _prefer([t["traj_id"] for t in elig if t["n_failed_exec"] + t["n_empty"] > 0], all_ids, K, rng),
        "no_repair": lambda rng: _prefer([t["traj_id"] for t in elig if t["n_turns"] == 1], all_ids, K, rng),
        "db_diverse": lambda rng: _db_diverse(elig, K, rng),
        "db_narrow": lambda rng: _db_narrow(elig, K, rng),
        "dedup": lambda rng: _dedup(elig, K, rng),
        "dup": lambda rng: _dup(elig, K, rng),
        "short": lambda rng: _by_quantile(elig, lambda t: t["n_out_tokens"], "low", K, rng),
        "long": lambda rng: _by_quantile(elig, lambda t: t["n_out_tokens"], "high", K, rng),
    }
    unknown = set(plan) - set(strategies)
    if unknown:
        raise ValueError(f"unknown strategies: {sorted(unknown)}")

    batches = []
    for name, count in plan.items():
        for rep in range(count):
            rng = random.Random(f"{seed}-{name}-{rep}")
            ids, pref_frac = strategies[name](rng)
            batches.append({"batch_id": f"{name}-{rep:02d}", "strategy": name,
                            "traj_ids": ids, "preferred_frac": pref_frac,
                            "covariates": covariates([by_id[i] for i in ids], rates)})
    return batches


def covariates(ts, rates) -> dict:
    return {
        "n_traj": len(ts),
        "n_unique_q": len({t["qid"] for t in ts}),
        "n_dbs": len({t["db_id"] for t in ts}),
        "mean_pass_rate": float(np.mean([rates[t["qid"]] for t in ts])),
        "repair_frac": float(np.mean([t["n_turns"] > 1 for t in ts])),
        "recovered_frac": float(np.mean([t["recovered"] for t in ts])),
        "mean_turns": float(np.mean([t["n_turns"] for t in ts])),
        "schema_ok_frac": float(np.mean([t["schema_ok_all"] for t in ts])),
        "mean_out_tokens": float(np.mean([t["n_out_tokens"] for t in ts])),
        "total_out_tokens": int(sum(t["n_out_tokens"] for t in ts)),
    }
