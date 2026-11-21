"""Phase 3 report: immediate (U^1) vs. long-horizon (U^H) utility of the carried sets.

U^1 = P(theta_1) - P(theta_0) from Phase 1; U^H = sum_h gamma^(h-1) [P(theta_h) - P(theta_{h-1})],
all measured as sampled pass rate on util-val. Writes <run_dir>/report.md.

python scripts/analyze_phase3.py --config configs/phase3.yaml
"""
import argparse
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

from rsi.analysis import catchup_test, reversal_test
from rsi.utils import load_config, read_json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/phase3.yaml")
    ap.add_argument("--iters", type=int, default=1000)
    args = ap.parse_args()
    cfg = load_config(args.config)
    run_dir = Path(cfg["run_dir"])
    plan = read_json(run_dir / "plan.json")
    k, split, gamma = plan["eval_k"], cfg["eval"]["split"], cfg["phase3"]["gamma"]
    src_ev = Path(plan["source_run"]) / f"eval_k{k}" / split
    p3_ev = run_dir / f"eval_k{k}" / split

    base = read_json(src_ev / "base.json")["correct"]
    qids = sorted(base)
    vec = lambda d: np.array([d[q] for q in qids], float)
    b0 = vec(base)
    H = plan["horizon"]
    sets, seeds = plan["sets"], plan["seeds"]
    # P[h][set][seed] = per-question pass rate after round h
    P, missing = defaultdict(dict), []
    for b in sets:
        for s in seeds:
            P[1][(b, s)] = vec(read_json(src_ev / f"{b}__s{s}.json")["correct"])
            for h in range(2, H + 1):
                f = p3_ev / f"r{h}__{b}__s{s}.json"
                if f.exists():
                    P[h][(b, s)] = vec(read_json(f)["correct"])
                else:
                    missing.append(f.name)
    if missing:
        raise SystemExit(f"{len(missing)} evaluations missing, e.g. {missing[:3]}")

    def gains(h):  # per-question gain of round h over round h-1: (sets, seeds, questions)
        prev = (lambda b, s: b0) if h == 1 else (lambda b, s: P[h - 1][(b, s)])
        return np.stack([np.stack([P[h][(b, s)] - prev(b, s) for s in seeds]) for b in sets])

    G = {h: gains(h) for h in range(1, H + 1)}
    U1 = G[1]
    UH = sum(gamma ** (h - 1) * G[h] for h in range(1, H + 1))
    u1, uh = U1.mean(axis=(1, 2)), UH.mean(axis=(1, 2))
    later = sum(gamma ** (h - 1) * G[h] for h in range(2, H + 1)).mean(axis=(1, 2))
    strat = plan["strategies"]

    L = [f"# Phase 3 report: H = {H}, rule = {plan['rule']}, {len(sets)} sets x {len(seeds)} seeds, "
         f"k = {k}, n = {len(qids)} questions", "",
         f"θ0 pass rate: {b0.mean():.4f}. Gains are in pass-rate points (x100).", ""]

    rt = reversal_test(U1, UH, n_iter=args.iters)
    lo, hi = rt["disattenuated_ci"]
    L += ["## Do immediate and long-horizon utility rank sets the same?", "",
          f"- Spearman(U^1, U^H) on full set means: {stats.spearmanr(u1, uh)[0]:.3f}",
          f"- Spearman(U^1, later-round gain U^H - U^1): {stats.spearmanr(u1, later)[0]:.3f} "
          "(negative = sets that win now gain less later)",
          f"- independent-measurement agreement: U^1 vs U^1 {rt['ceil_1']:.3f}, U^H vs U^H {rt['ceil_H']:.3f}, "
          f"U^1 vs U^H {rt['cross']:.3f}",
          f"- **noise-corrected (disattenuated) correlation: {rt['disattenuated']:.3f} "
          f"[95% {lo:.3f}, {hi:.3f}]**; 1 = same ranking, well below 1 = genuine rank reversal",
          f"- share of set pairs ordered differently: {100 * rt['flip_rate_cross']:.1f}% between U^1 and U^H "
          f"vs {100 * rt['flip_rate_noise']:.1f}% between two U^1 measurements (noise baseline)",
          f"- iterations with cross agreement below the U^1 ceiling: {100 * rt['p_cross_below_ceiling']:.0f}%", ""]
    verdict = ("RANK REVERSAL beyond noise" if hi < 0.9 else
               "NO evidence of reversal beyond noise" if lo > 0.9 else "INCONCLUSIVE (interval spans 0.9)")
    L += [f"**Verdict: {verdict}** (rule: upper 95% bound of the corrected correlation < 0.9)", ""]

    LATER = UH - U1
    ct = catchup_test(U1, LATER, n_iter=args.iters)
    clo, chi = ct["cross_ci"]
    L += ["## Catch-up: do sets that win round 1 gain less later?", "",
          f"- naive Spearman(U^1, later gain) = {ct['naive']:.3f} (biased negative by regression to the mean)",
          f"- cross-fitted (different seed and question half) = {ct['cross']:.3f} [95% {clo:.3f}, {chi:.3f}]; "
          f"negative in {100 * ct['p_cross_negative']:.0f}% of iterations",
          "- a cross-fitted value near 0 means the naive catch-up is mostly regression to the mean", ""]

    order1 = np.argsort(-u1)
    rankH = {i: r for r, i in enumerate(np.argsort(-uh), 1)}
    L += ["## Sets ranked by U^1", "",
          "| rank U^1 | set | strategy | U^1 | U^H | later gain | rank U^H |", "|---|---|---|---|---|---|---|"]
    L += [f"| {r} | {sets[i]} | {strat[sets[i]]} | {100 * u1[i]:+.2f} | {100 * uh[i]:+.2f} | "
          f"{100 * later[i]:+.2f} | {rankH[i]} |" for r, i in enumerate(order1, 1)]

    by = defaultdict(list)
    for i, b in enumerate(sets):
        by[strat[b]].append(i)
    L += ["", "## By strategy", "", "| strategy | sets | U^1 | later gain | U^H |", "|---|---|---|---|---|"]
    for s_, idx in sorted(by.items(), key=lambda kv: -uh[kv[1]].mean()):
        L.append(f"| {s_} | {len(idx)} | {100 * u1[idx].mean():+.2f} | {100 * later[idx].mean():+.2f} | "
                 f"{100 * uh[idx].mean():+.2f} |")

    batches = {b["batch_id"]: b for b in read_json(Path(plan["source_run"]) / "batches.json")}
    covs = ["mean_pass_rate", "n_dbs", "n_unique_q", "repair_frac", "mean_out_tokens"]
    L += ["", "## What predicts the later-round gain?", "", "| covariate | Spearman with U^1 | Spearman with later gain |",
          "|---|---|---|"]
    for c in covs:
        x = [batches[b]["covariates"][c] for b in sets]
        L.append(f"| {c} | {stats.spearmanr(x, u1)[0]:+.3f} | {stats.spearmanr(x, later)[0]:+.3f} |")

    gen_stats = []
    for h in range(2, H + 1):
        for b in sets:
            for s in seeds:
                f = run_dir / f"round{h}" / f"{b}__s{s}" / "stats.json"
                if f.exists():
                    gen_stats.append((h, read_json(f)))
    if gen_stats:
        L += ["", "## Self-generated rollouts in later rounds", ""]
        for h in range(2, H + 1):
            st = [g for hh, g in gen_stats if hh == h]
            if st:
                L.append(f"- round {h}: rollout correctness {np.mean([g['correct'] for g in st]):.3f}, "
                         f"questions solved {np.mean([g['questions_solved'] for g in st]):.3f} "
                         f"(mean over {len(st)} lineages)")

    (run_dir / "report.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
