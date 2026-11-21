"""BIRD official metric: greedy execution accuracy (EX) on the full dev set, overall and by
difficulty, for theta_0 and every round-H adapter of the frontier experiment. Resumable.

The agent keeps its execute-and-repair loop (up to eval.max_turns), as in training; report this as
"EX with execution feedback". Questions whose gold SQL cannot be executed count as wrong for every
model, as in the official evaluator.

python scripts/official_eval.py run    --config configs/frontier.yaml --round 3 --compile
python scripts/official_eval.py report --config configs/frontier.yaml --round 3
"""
import argparse
from collections import Counter
from itertools import combinations
from pathlib import Path

import numpy as np

from rsi.utils import load_config, read_json, read_jsonl, write_json


def targets(cfg, h):
    fr = cfg["frontier"]
    out = [("base", None)]
    for rule in fr["rules"]:
        for s in fr["seeds"]:
            p = Path(cfg["run_dir"]) / f"round{h}" / f"{rule}__s{s}" / "adapter"
            if (p / "adapter_config.json").exists():
                out.append((f"r{h}__{rule}__s{s}", p))
    return out


def run(cfg, args, out_dir, items):
    from vllm.lora.request import LoRARequest
    from rsi.rollout import make_llm, run_episodes

    todo = [t for t in targets(cfg, args.round) if not (out_dir / f"{t[0]}.json").exists()]
    if not todo:
        print("nothing to evaluate")
        return
    if args.compile:
        cfg["vllm"]["enforce_eager"] = False
    r, e = cfg["rollout"], cfg["eval"]
    llm = make_llm(cfg, enable_lora=True)
    for i, (name, path) in enumerate(todo):
        lora = LoRARequest(name, i + 1, str(path)) if path else None
        trajs = run_episodes(llm, items, n_samples=1, temperature=0.0, max_new_tokens=e["max_new_tokens"],
                             max_turns=e["max_turns"], lora_request=lora, exec_timeout=args.exec_timeout,
                             workers=r["workers"], max_rows=args.max_rows,
                             schema_max_chars=r["schema_max_chars"])
        correct = {t["qid"]: int(t["correct"]) for t in trajs}
        ex = sum(correct.values()) / len(correct)
        write_json(out_dir / f"{name}.json", {"name": name, "ex": ex, "n": len(correct), "correct": correct})
        print(f"{name}: EX={ex:.4f}", flush=True)


def report(cfg, args, out_dir, items):
    fr = cfg["frontier"]
    qids = [x["qid"] for x in items]
    diff = {x["qid"]: x.get("difficulty") or "all" for x in items}
    levels = [d for d in ("simple", "moderate", "challenging") if d in set(diff.values())]
    vec = lambda name: np.array([read_json(out_dir / f"{name}.json")["correct"][q] for q in qids], float)
    base = vec("base")
    rules = [r for r in fr["rules"]
             if all((out_dir / f"r{args.round}__{r}__s{s}.json").exists() for s in fr["seeds"])]
    M = {rule: np.stack([vec(f"r{args.round}__{rule}__s{s}") for s in fr["seeds"]]) for rule in rules}
    masks = {lv: np.array([diff[q] == lv for q in qids]) for lv in levels}
    n_fail = sum(1 for x in items if x.get("gold_failed"))

    L = [f"# BIRD dev, official metric (greedy EX with execution feedback), round {args.round}", "",
         f"{len(qids)} questions ({dict(Counter(diff.values()))}); {n_fail} with unexecutable gold SQL are "
         f"scored wrong for every model. Rules: mean over {len(fr['seeds'])} seeds (SD in brackets).", "",
         "| model | EX | " + " | ".join(levels) + " |", "|---|---|" + "---|" * len(levels),
         f"| θ0 | {100 * base.mean():.2f} | " + " | ".join(f"{100 * base[masks[lv]].mean():.2f}" for lv in levels) + " |"]
    for rule in rules:
        m = M[rule]
        L.append(f"| {rule} | {100 * m.mean():.2f} ({100 * m.mean(1).std():.2f}) | "
                 + " | ".join(f"{100 * m[:, masks[lv]].mean():.2f}" for lv in levels) + " |")

    rng = np.random.default_rng(0)
    n_s, n_q = len(fr["seeds"]), len(qids)
    boots = [(rng.integers(0, n_s, n_s), rng.integers(0, n_q, n_q)) for _ in range(args.boot)]
    L += ["", "## Paired differences (EX points; bootstrap over seeds and questions, 95% CI)", "",
          "| A - B | difference | 95% CI |", "|---|---|---|"]
    for a, b in combinations(rules, 2):
        d = [M[a][si][:, qi].mean() - M[b][si][:, qi].mean() for si, qi in boots]
        L.append(f"| {a} - {b} | {100 * (M[a].mean() - M[b].mean()):+.2f} | "
                 f"[{100 * np.quantile(d, .025):+.2f}, {100 * np.quantile(d, .975):+.2f}] |")
    for rule in rules:
        d = [M[rule][si][:, qi].mean() - base[qi].mean() for si, qi in boots]
        L.append(f"| {rule} - θ0 | {100 * (M[rule].mean() - base.mean()):+.2f} | "
                 f"[{100 * np.quantile(d, .025):+.2f}, {100 * np.quantile(d, .975):+.2f}] |")
    out = Path(cfg["run_dir"]) / f"report_official_{args.split}_r{args.round}.md"
    out.write_text("\n".join(L) + "\n")
    print("\n".join(L))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["run", "report"])
    ap.add_argument("--config", default="configs/frontier.yaml")
    ap.add_argument("--split", default="test_full")
    ap.add_argument("--round", type=int, default=3)
    ap.add_argument("--exec-timeout", type=float, default=30.0, help="per predicted query (official: 30 s)")
    ap.add_argument("--max-rows", type=int, default=2_000_000)
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--compile", action="store_true")
    args = ap.parse_args()
    cfg = load_config(args.config)
    items = read_jsonl(Path(cfg["data_dir"]) / f"{args.split}.jsonl")
    out_dir = Path(cfg["run_dir"]) / "eval_greedy" / args.split
    (run if args.stage == "run" else report)(cfg, args, out_dir, items)


if __name__ == "__main__":
    main()
