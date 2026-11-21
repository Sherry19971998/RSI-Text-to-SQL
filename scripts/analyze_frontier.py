"""Frontier experiment report: pass rate and coverage per rule and round, frontier movement on the
pool, and whether rule rankings change between round 1 and round H. Writes <run_dir>/report.md
(and curves.png when matplotlib is available).

Rule differences are paired within a seed (round-1 data is shared) and bootstrapped over seeds
and evaluation questions.

python scripts/analyze_frontier.py --config configs/frontier.yaml
"""
import argparse
from itertools import combinations
from pathlib import Path

import numpy as np

from rsi.utils import load_config, read_json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/frontier.yaml")
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--split", default=None, help="e.g. test (BIRD dev); default eval.split")
    args = ap.parse_args()
    cfg = load_config(args.config)
    fr, run_dir = cfg["frontier"], Path(cfg["run_dir"])
    split, k = args.split or cfg["eval"]["split"], fr["eval_k"]
    rules, seeds = fr["rules"], fr["seeds"]
    ev = run_dir / f"eval_k{k}" / split

    own_base = ev / "base.json"  # other splits: theta_0 evaluated by frontier.py eval --split
    if not own_base.exists() and not fr.get("base_eval"):
        raise SystemExit(f"no theta_0 evaluation in {ev}; run frontier.py eval first")
    base = read_json(own_base if own_base.exists() else Path(fr["base_eval"]) / split / "base.json")["correct"]
    any_run = sorted(ev.glob("r*__*.json"))
    first = read_json(any_run[0])["correct"] if any_run else base
    qids = sorted(q for q in base if q in first)  # eval_limit (smoke runs) scores a subset
    b0 = np.array([base[q] for q in qids], float)
    rounds = [h for h in range(1, fr["horizon"] + 1)
              if all((ev / f"r{h}__{r}__s{s}.json").exists() for r in rules for s in seeds)]
    if not rounds:
        raise SystemExit("no complete round evaluated yet")
    H = rounds[-1]
    # X[rule][h] = (seeds, questions) per-question pass rates; round 0 = theta_0 for every seed
    X = {r: {0: np.tile(b0, (len(seeds), 1))} for r in rules}
    for r in rules:
        for h in rounds:
            X[r][h] = np.stack([[read_json(ev / f"r{h}__{r}__s{s}.json")["correct"][q] for q in qids]
                                for s in seeds])
    acc = lambda m: m.mean()
    cov = lambda m: (m > 0).mean()

    L = [f"# Frontier experiment: rounds 1..{H} of {fr['horizon']}, rules {rules}, seeds {seeds}, "
         f"k = {k}, n = {len(qids)} eval questions", ""]
    L += [f"## Evaluation curves ({split})", "",
          "Pass rate = mean per-question pass rate over k samples; coverage = share of questions solved "
          f"at least once in {k} samples. Points, mean over seeds (seed SD in brackets).", "",
          "| rule | " + " | ".join(f"round {h} pass" for h in [0] + rounds) + " | "
          + " | ".join(f"round {h} cov" for h in [0] + rounds) + " |",
          "|---|" + "---|" * (2 * (len(rounds) + 1))]
    for r in rules:
        pa = [f"{100 * acc(X[r][h]):.2f} ({100 * X[r][h].mean(1).std():.2f})" for h in [0] + rounds]
        co = [f"{100 * cov(X[r][h]):.2f}" for h in [0] + rounds]
        L.append(f"| {r} | " + " | ".join(pa) + " | " + " | ".join(co) + " |")

    # pool frontier from generation stats
    L += ["", "## Frontier on the generation pool", "",
          "solved8 / solved32 = share of pool questions with >= 1 correct sample in the first 8 / all samples; "
          "newly = solved this round but in no earlier round of the lineage.", "",
          "| rule | " + " | ".join(f"round {h} solved8 / solved32 / newly" for h in range(1, H + 1)) + " |",
          "|---|" + "---|" * H]
    for r in rules:
        cells = []
        for h in range(1, H + 1):
            rr = fr.get("round1_alias", {}).get(r, r) if h == 1 else r   # aliased round-1 lineages
            st = [read_json(run_dir / f"round{h}" / f"{rr}__s{s}" / "stats.json") for s in seeds]
            nw = [x["n_newly_solved"] for x in st if x["n_newly_solved"] is not None]
            cells.append(f"{100 * np.mean([x['solved_frac_first_pass'] for x in st]):.1f} / "
                         f"{100 * np.mean([x['solved_frac_with_topup'] for x in st]):.1f} / "
                         + (f"{np.mean(nw):.0f}" if nw else "-"))
        L.append(f"| {r} | " + " | ".join(cells) + " |")

    # paired bootstrap of rule differences per round
    rng = np.random.default_rng(0)
    n_s, n_q = len(seeds), len(qids)
    boots = [(rng.integers(0, n_s, n_s), rng.integers(0, n_q, n_q)) for _ in range(args.boot)]

    def diff_ci(a, b, h, f):
        d = []
        for si, qi in boots:
            d.append(f(X[a][h][si][:, qi]) - f(X[b][h][si][:, qi]))
        return f(X[a][h]) - f(X[b][h]), np.quantile(d, 0.025), np.quantile(d, 0.975)

    L += ["", "## Pairwise rule differences (pass rate, points; paired by seed, bootstrap 95% CI)", "",
          "| A - B | " + " | ".join(f"round {h}" for h in rounds) + " | ranking changes? |",
          "|---|" + "---|" * (len(rounds) + 1)]
    for a, b in combinations(rules, 2):
        cells, signs, means = [], [], []
        for h in rounds:
            m, lo, hi = diff_ci(a, b, h, acc)
            cells.append(f"{100 * m:+.2f} [{100 * lo:+.2f}, {100 * hi:+.2f}]")
            signs.append(1 if lo > 0 else -1 if hi < 0 else 0)
            means.append(m)
        if signs[0] * signs[-1] == -1:
            flip = "yes, significant at both ends"
        elif np.sign(means[0]) != np.sign(means[-1]):
            flip = "sign change, not significant"
        else:
            flip = "no"
        L.append(f"| {a} - {b} | " + " | ".join(cells) + f" | {flip} |")

    L += ["", "## Pairwise rule differences (coverage, points)", "",
          "| A - B | " + " | ".join(f"round {h}" for h in rounds) + " |", "|---|" + "---|" * len(rounds)]
    for a, b in combinations(rules, 2):
        cells = []
        for h in rounds:
            m, lo, hi = diff_ci(a, b, h, cov)
            cells.append(f"{100 * m:+.2f} [{100 * lo:+.2f}, {100 * hi:+.2f}]")
        L.append(f"| {a} - {b} | " + " | ".join(cells) + " |")

    r1 = sorted(rules, key=lambda r: -acc(X[r][rounds[0]]))
    rH = sorted(rules, key=lambda r: -acc(X[r][H]))
    L += ["", f"Rule ranking by pass rate after round {rounds[0]}: {' > '.join(r1)}",
          f"Rule ranking by pass rate after round {H}: {' > '.join(rH)}", ""]

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 2, figsize=(10, 4))
        xs = [0] + rounds
        for r in rules:
            for ax, f in zip(axes, (acc, cov)):
                ys = [100 * f(X[r][h]) for h in xs]
                ax.plot(xs, ys, marker="o", label=r)
        for ax, t in zip(axes, ("Pass rate (k samples), %", f"Coverage (solved in {k}), %")):
            ax.set_title(t); ax.set_xlabel("round"); ax.set_xticks(xs); ax.grid(alpha=0.3)
        axes[0].legend()
        fig.tight_layout()
        fig.savefig(run_dir / "curves.png", dpi=150)
        L.append(f"Curves saved to {run_dir / 'curves.png'}")
    except ImportError:
        pass

    (run_dir / ("report.md" if split == cfg["eval"]["split"] else f"report_{split}.md")).write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
