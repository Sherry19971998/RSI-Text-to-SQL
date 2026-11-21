"""Phase 1 robustness checks on existing eval results (CPU only, no GPU needed).

1. Utility variation among random batches only (no designed strategy differences).
2. Split-half over eval questions: do batch rankings replicate on disjoint question halves?
3. Seed reliability: do batch rankings replicate across training seeds?
4. Covariate baseline: how much of mean dP do simple batch statistics explain (in-sample
   and leave-one-batch-out)? Compare with the reliability ceiling from 2-3.

Writes <run_dir>/robustness.md.

python scripts/robustness.py --config configs/default.yaml
"""
import argparse
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

from rsi.analysis import one_way_anova
from rsi.utils import load_config, read_json

COVS = ["mean_pass_rate", "n_dbs", "n_unique_q", "mean_out_tokens", "repair_frac"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--splits", type=int, default=500)
    ap.add_argument("--metric", choices=["acc", "pass", "nll"], default="acc",
                    help="acc: greedy 0/1 correctness; pass: sampled pass rate (evaluate.py --samples K); "
                         "nll: -(gold-SQL NLL), from evaluate_nll.py")
    ap.add_argument("--k", type=int, default=4, help="samples per question for --metric pass")
    args = ap.parse_args()
    cfg = load_config(args.config)
    run_dir = Path(cfg["run_dir"])
    split = cfg["eval"]["split"]
    ev = run_dir / {"acc": "eval", "pass": f"eval_k{args.k}", "nll": "nll"}[args.metric] / split
    key = "nll" if args.metric == "nll" else "correct"
    sign = -1.0 if args.metric == "nll" else 1.0  # lower NLL = better, so gains stay positive
    batches = {b["batch_id"]: b for b in read_json(run_dir / "batches.json")}

    base = read_json(ev / "base.json")
    qids = sorted(base[key])
    base_v = sign * np.array([base[key][q] for q in qids], float)
    runs = defaultdict(dict)  # batch -> seed -> per-question correctness
    for p in sorted(ev.glob("*__s*.json")):
        r = read_json(p)
        bid, seed = r["name"].rsplit("__s", 1)
        runs[bid][int(seed)] = sign * np.array([r[key][q] for q in qids], float)
    bids = sorted(runs)
    seeds = sorted({s for b in bids for s in runs[b]})
    # per-question gain matrix: batch x seed x question
    G = np.stack([np.stack([runs[b][s] - base_v for s in seeds]) for b in bids])
    mean_dp = G.mean(axis=(1, 2))
    L = [f"# Robustness: {run_dir.name}, metric={args.metric} "
         f"({len(bids)} batches x {len(seeds)} seeds, n={len(qids)} questions)", ""]
    if args.metric != "acc":
        acc_dir = run_dir / "eval" / split
        if (acc_dir / "base.json").exists():
            ab = read_json(acc_dir / "base.json")["correct"]
            acc_dp = []
            for b in bids:
                vals = [np.mean([read_json(acc_dir / f"{b}__s{s}.json")["correct"][q] - ab[q] for q in ab])
                        for s in seeds]
                acc_dp.append(np.mean(vals))
            L += ["Gain = reduction in mean gold-SQL token NLL (positive = better)." if args.metric == "nll"
                  else f"Gain = change in per-question pass rate over {args.k} samples.", ""]
            acc_dp = np.array(acc_dp)
        else:
            acc_dp = None
    if args.metric != "acc" and acc_dp is not None:
        r, p = stats.spearmanr(mean_dp, acc_dp)
        strat_all = sorted({batches[b]["strategy"] for b in bids})
        sa = [np.mean([mean_dp[i] for i, b in enumerate(bids) if batches[b]["strategy"] == s]) for s in strat_all]
        sb = [np.mean([acc_dp[i] for i, b in enumerate(bids) if batches[b]["strategy"] == s]) for s in strat_all]
        L += ["## 0. Agreement with greedy accuracy gains", "",
              f"- batch level: Spearman({args.metric} gain, greedy accuracy dP) = {r:.3f} (p={p:.3g})",
              f"- strategy level: Spearman = {stats.spearmanr(sa, sb)[0]:.3f} over {len(strat_all)} strategies", ""]

    # 1. random batches only
    L += ["## 1. Variation among random batches only", ""]
    for label, sel in [("random", lambda b: batches[b]["strategy"] == "random"),
                       ("structured", lambda b: batches[b]["strategy"] != "random")]:
        groups = [G[i].mean(axis=1) for i, b in enumerate(bids) if sel(b)]
        if len(groups) >= 2:
            a = one_way_anova(groups)
            L.append(f"- {label}: {a['n_batches']} batches, ICC={a['icc']:.3f}, F={a['F']:.2f}, p={a['p']:.2e}, "
                     f"between-batch SD={a['sd_between']:.4f}, seed SD={a['sd_within']:.4f}")
    L += ["", "ICC well above 0 for random batches means utility differs even without designed "
          "strategy differences, i.e. correctness-matched sampling alone does not control utility.", ""]

    # 2. split-half over questions
    rng = np.random.default_rng(0)
    rhos, rhos_rand = [], []
    rand_idx = [i for i, b in enumerate(bids) if batches[b]["strategy"] == "random"]
    for _ in range(args.splits):
        perm = rng.permutation(len(qids))
        h1, h2 = perm[: len(qids) // 2], perm[len(qids) // 2:]
        a, b = G[:, :, h1].mean(axis=(1, 2)), G[:, :, h2].mean(axis=(1, 2))
        rhos.append(stats.spearmanr(a, b)[0])
        if len(rand_idx) >= 4:
            rhos_rand.append(stats.spearmanr(a[rand_idx], b[rand_idx])[0])
    def summ(x):
        x = np.array(x)
        m = float(np.median(x))
        return f"median rho={m:.3f} [2.5%={np.quantile(x, .025):.3f}, 97.5%={np.quantile(x, .975):.3f}], " \
               f"Spearman-Brown full-set reliability={2 * m / (1 + m):.3f}"
    L += ["## 2. Split-half over evaluation questions", "",
          f"Batch rankings computed on two disjoint random halves of the questions ({args.splits} splits).", "",
          f"- all batches: {summ(rhos)}"]
    if rhos_rand:
        L.append(f"- random batches only: {summ(rhos_rand)}")
    L += ["", "High agreement means the ranking reflects the batches, not the particular questions evaluated.", ""]

    # 3. seed reliability
    per_seed = G.mean(axis=2)  # batch x seed
    pairs = [(i, j) for i in range(len(seeds)) for j in range(i + 1, len(seeds))]
    rs = [stats.spearmanr(per_seed[:, i], per_seed[:, j])[0] for i, j in pairs]
    r1 = float(np.mean(rs))
    k = len(seeds)
    L += ["## 3. Seed reliability", "",
          f"- mean pairwise Spearman between single-seed rankings: {r1:.3f}",
          f"- reliability of the {k}-seed mean (Spearman-Brown): {k * r1 / (1 + (k - 1) * r1):.3f}", "",
          "This is the ceiling on how well any predictor can rank batches against these labels.", ""]

    # 4. covariate baseline
    X = np.array([[batches[b]["covariates"][c] for c in COVS] for b in bids], float)
    X = (X - X.mean(0)) / np.where(X.std(0) > 0, X.std(0), 1)
    X1 = np.hstack([np.ones((len(bids), 1)), X])
    beta, *_ = np.linalg.lstsq(X1, mean_dp, rcond=None)
    r2 = 1 - ((mean_dp - X1 @ beta) ** 2).sum() / ((mean_dp - mean_dp.mean()) ** 2).sum()
    loo = np.empty(len(bids))
    for i in range(len(bids)):
        m = np.arange(len(bids)) != i
        bi, *_ = np.linalg.lstsq(X1[m], mean_dp[m], rcond=None)
        loo[i] = X1[i] @ bi
    loo_r2 = 1 - ((mean_dp - loo) ** 2).sum() / ((mean_dp - mean_dp.mean()) ** 2).sum()
    L += ["## 4. Covariate baseline (preview of a Phase 2 'process-score' predictor)", "",
          f"Linear model of mean dP on standardized {', '.join(COVS)}:", "",
          f"- in-sample R^2 = {r2:.3f}",
          f"- leave-one-batch-out R^2 = {loo_r2:.3f}, Spearman(pred, actual) = {stats.spearmanr(loo, mean_dp)[0]:.3f}", "",
          "| covariate | standardized coef |", "|---|---|"]
    L += [f"| {c} | {b:+.4f} |" for c, b in zip(COVS, beta[1:])]
    L += ["", "Utility left unexplained by these cheap statistics (up to the reliability ceiling) is what a "
          "learned verifier with gradient/process features would need to capture.", ""]

    # 5. strategy-level split-half: does a coarser grouping generalize across questions?
    strat = sorted({batches[b]["strategy"] for b in bids})
    s_idx = {s: [i for i, b in enumerate(bids) if batches[b]["strategy"] == s] for s in strat}
    srhos, hard_easy = [], []
    for _ in range(args.splits):
        perm = rng.permutation(len(qids))
        h1, h2 = perm[: len(qids) // 2], perm[len(qids) // 2:]
        a = [G[s_idx[s]][:, :, h1].mean() for s in strat]
        b = [G[s_idx[s]][:, :, h2].mean() for s in strat]
        srhos.append(stats.spearmanr(a, b)[0])
        if "hard" in s_idx and "easy" in s_idx:
            d1 = G[s_idx["hard"]][:, :, h1].mean() - G[s_idx["easy"]][:, :, h1].mean()
            d2 = G[s_idx["hard"]][:, :, h2].mean() - G[s_idx["easy"]][:, :, h2].mean()
            hard_easy.append((d1 > 0) and (d2 > 0))
    L += ["## 5. Strategy-level split-half", "",
          f"- {len(strat)} strategies: {summ(srhos)}"]
    if hard_easy:
        L.append(f"- hard > easy on both halves in {100 * np.mean(hard_easy):.0f}% of splits")
    L.append("")

    if args.metric == "acc":
        # 6. question-level churn: how many answers flip per run, and do flips repeat across seeds?
        up = (G > 0).mean(axis=2)    # batch x seed: fraction of questions fixed
        down = (G < 0).mean(axis=2)  # fraction broken
        agree = []
        for i in range(len(bids)):
            for s1, s2 in pairs:
                f1, f2 = G[i, s1] != 0, G[i, s2] != 0
                agree.append((f1 & f2).sum() / max(1, (f1 | f2).sum()))
        cross = []
        for i in range(len(bids)):
            j = (i + 1) % len(bids)
            f1, f2 = G[i, 0] != 0, G[j, 0] != 0
            cross.append((f1 & f2).sum() / max(1, (f1 | f2).sum()))
        L += ["## 6. Question-level churn", "",
              f"- per run: {100 * up.mean():.1f}% of questions fixed, {100 * down.mean():.1f}% broken "
              f"(net {100 * (up - down).mean():+.2f} points)",
              f"- overlap (Jaccard) of flipped questions, same batch / different seeds: {np.mean(agree):.3f}",
              f"- overlap of flipped questions, different batches / same seed: {np.mean(cross):.3f}",
              "",
              "Churn much larger than the net gain, with flips repeating within a batch, means batch-level dP "
              "on a fixed question set is dominated by which particular questions each batch flips.", ""]

    # 7. covariate model fitted on one half, evaluated on the other
    xr = []
    for _ in range(min(args.splits, 200)):
        perm = rng.permutation(len(qids))
        h1, h2 = perm[: len(qids) // 2], perm[len(qids) // 2:]
        y1, y2 = G[:, :, h1].mean(axis=(1, 2)), G[:, :, h2].mean(axis=(1, 2))
        bh, *_ = np.linalg.lstsq(X1, y1, rcond=None)
        xr.append(stats.spearmanr(X1 @ bh, y2)[0])
    pr = [stats.spearmanr(X[:, 0], G[:, :, rng.permutation(len(qids))[: len(qids) // 2]].mean(axis=(1, 2)))[0]
          for _ in range(200)]
    L += ["## 7. Covariate model across question halves", "",
          f"- fit on half A, Spearman with half B: median={np.median(xr):.3f} "
          f"[2.5%={np.quantile(xr, .025):.3f}, 97.5%={np.quantile(xr, .975):.3f}]",
          f"- {COVS[0]} alone vs. dP on a random half: median Spearman={np.median(pr):.3f}", "",
          "A positive cross-half correlation means batch statistics capture a generalizable part of utility "
          "even if individual batch rankings do not replicate.", ""]

    out = run_dir / "robustness.md"
    out.write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
