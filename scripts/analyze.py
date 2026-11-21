"""Phase 0 / Phase 1 report: noise floor, utility variance across equally-correct batches,
covariate checks, go/no-go verdict. Writes <run_dir>/report.md and runs.csv.

python scripts/analyze.py --config configs/phase0.yaml
"""
import argparse
import csv
from collections import defaultdict
from pathlib import Path

import numpy as np

from rsi.analysis import one_way_anova, paired_bootstrap, spearman_table
from rsi.utils import load_config, read_json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--split", default=None)
    args = ap.parse_args()
    cfg = load_config(args.config)
    a_cfg = cfg["analysis"]
    split = args.split or cfg["eval"]["split"]
    run_dir = Path(cfg["run_dir"])
    ev_dir = run_dir / "eval" / split
    batches = {b["batch_id"]: b for b in read_json(run_dir / "batches.json")}

    base = read_json(ev_dir / "base.json")
    qids = sorted(base["correct"])
    vec = lambda r: np.array([r["correct"][q] for q in qids])
    b_vec = vec(base)
    n = len(qids)
    L = [f"# Report: {run_dir.name} ({split}, n={n})", ""]
    L += [f"theta_0 accuracy: **{base['acc']:.4f}**  "
          f"(binomial SE of a single accuracy: {np.sqrt(base['acc'] * (1 - base['acc']) / n):.4f})", ""]

    reps = sorted(ev_dir.glob("base_r*.json"))
    if reps:
        agree = [float((vec(read_json(p)) == b_vec).mean()) for p in reps]
        L += [f"Greedy re-run agreement with base: {', '.join(f'{x:.4f}' for x in agree)} "
              "(should be ~1.0; lower means decoding nondeterminism adds eval noise)", ""]

    rows = []
    for p in sorted(ev_dir.glob("*__s*.json")):
        r = read_json(p)
        bid, seed = r["name"].rsplit("__s", 1)
        d, lo, hi = paired_bootstrap(vec(r), b_vec, a_cfg["bootstrap"])
        meta_p = run_dir / "adapters" / r["name"] / "train_meta.json"
        meta = read_json(meta_p) if meta_p.exists() else {}
        rows.append({"batch_id": bid, "strategy": batches[bid]["strategy"], "seed": int(seed),
                     "acc": r["acc"], "dP": d, "ci_lo": lo, "ci_hi": hi,
                     "train_loss": meta.get("train_loss"), **batches[bid]["covariates"]})
    if not rows:
        print("no adapter evaluations found")
        return
    with open(run_dir / "runs.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    by_batch = defaultdict(list)
    for r in rows:
        by_batch[r["batch_id"]].append(r["dP"])
    L += ["## Per-batch dP = P(theta_1^B) - P(theta_0)", "",
          "| batch | strategy | seeds | mean dP | sd over seeds | min | max |",
          "|---|---|---|---|---|---|---|"]
    for bid in sorted(by_batch, key=lambda k: -np.mean(by_batch[k])):
        v = np.array(by_batch[bid])
        L.append(f"| {bid} | {batches[bid]['strategy']} | {len(v)} | {v.mean():+.4f} | "
                 f"{v.std(ddof=1) if len(v) > 1 else float('nan'):.4f} | {v.min():+.4f} | {v.max():+.4f} |")
    sig = sum(r["ci_lo"] > 0 or r["ci_hi"] < 0 for r in rows)
    L += ["", f"Runs whose paired-bootstrap 95% CI excludes 0: {sig}/{len(rows)}", ""]

    by_strat = defaultdict(list)
    for bid, v in by_batch.items():
        by_strat[batches[bid]["strategy"]].append(np.mean(v))
    L += ["## Mean dP by strategy", ""] + [
        f"- {s}: {np.mean(v):+.4f} (n_batches={len(v)})"
        for s, v in sorted(by_strat.items(), key=lambda kv: -np.mean(kv[1]))] + [""]

    verdict = "INSUFFICIENT DATA"
    multi = [v for v in by_batch.values() if len(v) > 1]
    if len(by_batch) >= 2 and multi:
        a = one_way_anova(list(by_batch.values()))
        L += ["## Is utility variation above noise?", "",
              f"- seed noise (within-batch SD of dP): **{a['sd_within']:.4f}**",
              f"- between-batch SD of true utility:  **{a['sd_between']:.4f}**",
              f"- ICC (share of variance due to batch): **{a['icc']:.3f}**",
              f"- one-way ANOVA: F={a['F']:.2f}, p={a['p']:.2e} "
              f"({a['n_batches']} batches, {a['n_runs']} runs)", ""]
        go = a["icc"] >= a_cfg["icc_go"] and a["p"] <= a_cfg["p_go"]
        verdict = "GO" if go else "NO-GO"
        L += [f"**Verdict: {verdict}** (thresholds: ICC >= {a_cfg['icc_go']}, p <= {a_cfg['p_go']})", ""]

    bids = list(by_batch)
    if len(bids) >= 4:
        y = [np.mean(by_batch[b]) for b in bids]
        covs = {k: [batches[b]["covariates"][k] for b in bids] for k in batches[bids[0]]["covariates"]}
        L += ["## Confound check: Spearman(mean dP, covariate)", "",
              "If one covariate (e.g. tokens) explains almost all of dP, utility is mostly a size effect.", ""]
        L += [f"- {k}: rho={r:+.3f} (p={p:.3f})" for k, (r, p) in spearman_table(covs, y).items()]

    (run_dir / "report.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
