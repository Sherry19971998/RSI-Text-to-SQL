"""Generate theta_0 rollouts on the pool split (n_samples per question).

python scripts/generate_pool.py --config configs/default.yaml [--limit 50]
"""
import argparse
from collections import Counter
from pathlib import Path

from rsi.rollout import make_llm, run_episodes
from rsi.utils import load_config, read_jsonl, write_jsonl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--limit", type=int, default=None, help="smoke test on first N questions")
    args = ap.parse_args()
    cfg = load_config(args.config)
    r = cfg["rollout"]
    items = read_jsonl(Path(cfg["data_dir"]) / "pool.jsonl")[:args.limit]

    llm = make_llm(cfg, enable_lora=False)
    trajs = run_episodes(llm, items, n_samples=r["n_samples"], temperature=r["temperature"],
                         top_p=r["top_p"], max_new_tokens=r["max_new_tokens"],
                         max_turns=r["max_turns"], exec_timeout=r["exec_timeout"],
                         workers=r["workers"], schema_max_chars=r["schema_max_chars"],
                         seed=r["seed"])
    out = Path(cfg["pool_rollouts"])
    if args.limit:
        out = out.with_name(out.stem + f"_limit{args.limit}.jsonl")
    write_jsonl(out, trajs)

    n = len(trajs)
    print(f"wrote {n} trajectories -> {out}")
    print(f"  correct      {sum(t['correct'] for t in trajs) / n:.3f}")
    print(f"  safe_all     {sum(t['safe_all'] for t in trajs) / n:.3f}")
    print(f"  recovered    {sum(t['recovered'] for t in trajs) / n:.3f}")
    print(f"  turns        {dict(Counter(t['n_turns'] for t in trajs))}")
    q_any = len({t['qid'] for t in trajs if t['correct']})
    print(f"  questions with >=1 correct: {q_any}/{len(items)}")


if __name__ == "__main__":
    main()
