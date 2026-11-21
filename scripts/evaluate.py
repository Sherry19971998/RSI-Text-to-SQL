"""Evaluation of theta_0 and every trained adapter on a held-out split. One vLLM engine
serves all adapters (LoRA hot-swap). Resumable; shard with --shard/--num-shards.

Greedy (default): one decode per question, `correct` is 0/1.
Sampled (--samples K): K decodes per question at --temperature, `correct` is the per-question
pass rate in [0, 1]. Sampling seeds are identical across adapters (common random numbers),
so differences between adapters are not inflated by sampling noise. Results go to eval_k{K}/.

python scripts/evaluate.py --config configs/phase0.yaml --repeat-base 2
python scripts/evaluate.py --config configs/default.yaml --samples 4
"""
import argparse
from collections import defaultdict
from pathlib import Path

from rsi.rollout import make_llm, run_episodes
from rsi.utils import load_config, read_jsonl, write_json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--split", default=None, help="default: eval.split from config")
    ap.add_argument("--repeat-base", type=int, default=1,
                    help="evaluate theta_0 N times to measure decoding nondeterminism")
    ap.add_argument("--samples", type=int, default=1, help=">1: sampled pass rate instead of greedy")
    ap.add_argument("--temperature", type=float, default=0.8, help="used only with --samples > 1")
    ap.add_argument("--compile", action="store_true",
                    help="override vllm.enforce_eager=false (CUDA graphs; faster if it starts)")
    ap.add_argument("--limit", type=int, default=None,
                    help="smoke test: first N questions, base + first adapter, separate output dir")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--num-shards", type=int, default=1)
    args = ap.parse_args()
    cfg = load_config(args.config)
    if args.compile:
        cfg["vllm"]["enforce_eager"] = False
    split = args.split or cfg["eval"]["split"]
    run_dir = Path(cfg["run_dir"])
    items = read_jsonl(Path(cfg["data_dir"]) / f"{split}.jsonl")[:args.limit]
    sub = "eval" if args.samples == 1 else f"eval_k{args.samples}"
    if args.limit:
        sub += "_smoke"
    out_dir = run_dir / sub / split

    targets = [("base" if r == 0 else f"base_r{r}", None) for r in range(args.repeat_base)]
    adapters = sorted(p for p in (run_dir / "adapters").glob("*")
                      if (p / "adapter_config.json").exists())
    targets += [(p.name, p) for p in adapters]
    if args.limit:
        targets = targets[:2]
    targets = [t for t in targets[args.shard::args.num_shards]
               if args.limit or not (out_dir / f"{t[0]}.json").exists()]
    if not targets:
        print("nothing to evaluate")
        return

    from vllm.lora.request import LoRARequest
    llm = make_llm(cfg, enable_lora=True)
    r, e = cfg["rollout"], cfg["eval"]
    temperature = 0.0 if args.samples == 1 else args.temperature
    for idx, (name, path) in enumerate(targets):
        # vLLM caches adapters by int id; ids must be unique and stable within this process.
        lora = LoRARequest(name, idx + 1, str(path)) if path else None
        trajs = run_episodes(llm, items, n_samples=args.samples, temperature=temperature,
                             top_p=1.0, max_new_tokens=e["max_new_tokens"], max_turns=e["max_turns"],
                             lora_request=lora, exec_timeout=r["exec_timeout"],
                             workers=r["workers"], schema_max_chars=r["schema_max_chars"],
                             seed=r["seed"])
        hits = defaultdict(list)
        for t in trajs:
            hits[t["qid"]].append(int(t["correct"]))
        correct = {q: (v[0] if args.samples == 1 else sum(v) / len(v)) for q, v in hits.items()}
        acc = sum(correct.values()) / len(correct)
        write_json(out_dir / f"{name}.json", {
            "name": name, "split": split, "samples": args.samples, "temperature": temperature,
            "acc": acc, "n": len(correct), "correct": correct,
            "mean_turns": sum(t["n_turns"] for t in trajs) / len(trajs),
            "exec_fail_final": sum(not t["turns"][-1]["ok"] for t in trajs) / len(trajs),
        })
        print(f"{name}: acc={acc:.4f}", flush=True)


if __name__ == "__main__":
    main()
