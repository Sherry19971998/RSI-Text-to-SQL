"""Phase 0/1 statistics: does batch identity explain dP beyond seed + eval noise?"""
from __future__ import annotations

import numpy as np
from scipy import stats


def paired_bootstrap(a: np.ndarray, b: np.ndarray, n_boot=2000, seed=0):
    """Mean of (a - b) over aligned per-question 0/1 outcomes, with 95% CI."""
    d = a.astype(float) - b.astype(float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(d), size=(n_boot, len(d)))
    boots = d[idx].mean(axis=1)
    return float(d.mean()), float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))


def one_way_anova(groups: list) -> dict:
    """Random-effects one-way ANOVA. groups: list of arrays (dP per seed, one per batch).
    Returns F, p, within-batch SD (seed noise), between-batch SD, ICC(1)."""
    groups = [np.asarray(g, float) for g in groups if len(g) > 0]
    k = np.array([len(g) for g in groups])
    N, G = k.sum(), len(groups)
    if G < 2 or N <= G:
        raise ValueError("need >= 2 batches and >= 2 seeds in some batch")
    grand = np.concatenate(groups).mean()
    means = np.array([g.mean() for g in groups])
    ssb = float((k * (means - grand) ** 2).sum())
    ssw = float(sum(((g - g.mean()) ** 2).sum() for g in groups))
    msb, msw = ssb / (G - 1), ssw / (N - G)
    F = msb / msw if msw > 0 else float("inf")
    p = float(stats.f.sf(F, G - 1, N - G)) if np.isfinite(F) else 0.0
    n0 = (N - (k ** 2).sum() / N) / (G - 1)
    var_b = max(0.0, (msb - msw) / n0)
    icc = var_b / (var_b + msw) if (var_b + msw) > 0 else 0.0
    return {"F": F, "p": p, "sd_within": float(np.sqrt(msw)), "sd_between": float(np.sqrt(var_b)),
            "icc": float(icc), "n_batches": G, "n_runs": int(N)}


def spearman_table(xs: dict, y) -> dict:
    out = {}
    for name, x in xs.items():
        x = np.asarray(x, float)
        if np.allclose(x, x[0]):
            continue
        r, p = stats.spearmanr(x, y)
        out[name] = (float(r), float(p))
    return out


def reversal_test(U1: np.ndarray, UH: np.ndarray, n_iter: int = 1000, seed: int = 0) -> dict:
    """Do immediate (U1) and long-horizon (UH) utility rank sets differently beyond noise?

    U1, UH: per-question gains, shape (sets, seeds, questions). Each iteration draws a random
    question split (A, B) and two different seeds (a, b), so every correlation compares two
    independent measurements (different training runs, different questions):
      ceil_1 = rank corr of U1[a, A] with U1[b, B]   (U1 measured twice: noise-only agreement)
      ceil_H = rank corr of UH[a, A] with UH[b, B]
      cross  = rank corr of U1[a, A] with UH[b, B]
    Disattenuated rho = mean(cross) / sqrt(mean(ceil_1) * mean(ceil_H)); about 1 means the two
    utilities rank sets the same and any observed reversal is noise; well below 1 means genuine
    rank reversal. Pairwise reversal rates use Kendall tau: share of set pairs ordered differently.
    """
    rng = np.random.default_rng(seed)
    n_sets, n_seeds, n_q = U1.shape
    if n_seeds < 2:
        raise ValueError("need >= 2 seeds per set")
    c1, cH, cx, flip_noise, flip_cross = [], [], [], [], []
    for _ in range(n_iter):
        perm = rng.permutation(n_q)
        A, B = perm[: n_q // 2], perm[n_q // 2:]
        a, b = rng.choice(n_seeds, 2, replace=False)
        u1a, u1b = U1[:, a, A].mean(1), U1[:, b, B].mean(1)
        uha, uhb = UH[:, a, A].mean(1), UH[:, b, B].mean(1)
        c1.append(stats.spearmanr(u1a, u1b)[0])
        cH.append(stats.spearmanr(uha, uhb)[0])
        cx.append(stats.spearmanr(u1a, uhb)[0])
        flip_noise.append((1 - stats.kendalltau(u1a, u1b)[0]) / 2)
        flip_cross.append((1 - stats.kendalltau(u1a, uhb)[0]) / 2)
    c1, cH, cx = map(np.asarray, (c1, cH, cx))
    denom = np.sqrt(max(c1.mean(), 1e-9) * max(cH.mean(), 1e-9))
    boot = []
    for _ in range(1000):  # bootstrap the iteration means for an interval on the ratio
        i = rng.integers(0, n_iter, n_iter)
        boot.append(cx[i].mean() / np.sqrt(max(c1[i].mean(), 1e-9) * max(cH[i].mean(), 1e-9)))
    return {
        "ceil_1": float(c1.mean()), "ceil_H": float(cH.mean()), "cross": float(cx.mean()),
        "disattenuated": float(cx.mean() / denom),
        "disattenuated_ci": (float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))),
        "p_cross_below_ceiling": float(np.mean(cx < c1)),
        "flip_rate_noise": float(np.mean(flip_noise)), "flip_rate_cross": float(np.mean(flip_cross)),
    }


def catchup_test(U1: np.ndarray, LATER: np.ndarray, n_iter: int = 1000, seed: int = 0) -> dict:
    """Is the later-round gain lower for sets with a high U1, beyond regression to the mean?

    LATER = P(theta_H) - P(theta_1) shares P(theta_1) with U1 = P(theta_1) - P(theta_0), so noise
    in P(theta_1) alone makes corr(U1, LATER) negative. Cross-fitting removes that: U1 from seed a
    on question half A against LATER from seed b on half B (independent runs and questions).
    Shapes: (sets, seeds, questions). Returns the naive and cross-fitted Spearman correlations."""
    rng = np.random.default_rng(seed)
    n_sets, n_seeds, n_q = U1.shape
    naive = float(stats.spearmanr(U1.mean(axis=(1, 2)), LATER.mean(axis=(1, 2)))[0])
    cross = []
    for _ in range(n_iter):
        perm = rng.permutation(n_q)
        A, B = perm[: n_q // 2], perm[n_q // 2:]
        a, b = rng.choice(n_seeds, 2, replace=False)
        cross.append(stats.spearmanr(U1[:, a, A].mean(1), LATER[:, b, B].mean(1))[0])
    cross = np.asarray(cross)
    boot = [cross[rng.integers(0, n_iter, n_iter)].mean() for _ in range(1000)]
    return {"naive": naive, "cross": float(cross.mean()),
            "cross_ci": (float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))),
            "p_cross_negative": float(np.mean(cross < 0))}
