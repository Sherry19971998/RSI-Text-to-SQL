"""Phase 3: multi-round RSI branches from Phase 1 sets.

Each lineage (set B, seed s) starts from the Phase 1 adapter theta_1(B, s). Every later round:
  gen    theta_{h-1} generates rollouts on the pool; keep only the K selected by the fixed rule
  train  continue training theta_{h-1}'s LoRA on that selection with the same seed -> theta_h
  eval   sampled pass rate (k samples per question) of theta_h on util-val
Stages are separate processes (vLLM and training never share the GPU); each is resumable.

python scripts/phase3.py plan  --config configs/phase3.yaml
python scripts/phase3.py gen   --config configs/phase3.yaml --round 2 [--compile]
python scripts/phase3.py train --config configs/phase3.yaml --round 2
python scripts/phase3.py eval  --config configs/phase3.yaml --round 2 [--compile]
(or: bash scripts/run_phase3.sh)
"""
import argparse
import random
from collections import defaultdict
from pathlib import Path

from rsi.batches import build_batches
from rsi.utils import load_config, read_json, read_jsonl, write_json, write_jsonl


def lineages(plan):
    return [(b, s) for b in plan["sets"] for s in plan["seeds"]]


def lname(b, s):
    return f"{b}__s{s}"


def adapter_dir(cfg, plan, h, b, s):
    if h == 1:
        return Path(plan["source_run"]) / "adapters" / lname(b, s)
    return Path(cfg["run_dir"]) / f"round{h}" / lname(b, s) / "adapter"


def make_plan(cfg):
    p3 = cfg["phase3"]
    src = Path(p3["source_run"])
    batches = read_json(src / "batches.json")
    by_strat = defaultdict(list)
    for b in batches:
        by_strat[b["strategy"]].append(b["batch_id"])
    rng = random.Random(p3["plan_seed"])
    sets = []
    for strat in sorted(by_strat):
        ids = sorted(by_strat[strat])
        n = p3["random_sets"] if strat == "random" else p3["per_strategy"]
        sets += sorted(rng.sample(ids, min(n, len(ids))))
    missing = [lname(b, s) for b in sets for s in p3["seeds"]
               if not (src / "adapters" / lname(b, s) / "adapter_config.json").exists()]
    if missing:
        raise SystemExit(f"missing round-1 adapters: {missing[:5]} ...")
    plan = {"source_run": str(src), "sets": sets, "seeds": p3["seeds"], "horizon": p3["horizon"],
            "rule": p3["rule"], "gen_questions": p3["gen_questions"], "eval_k": p3["eval_k"],
            "strategies": {b["batch_id"]: b["strategy"] for b in batches if b["batch_id"] in sets}}
    write_json(Path(cfg["run_dir"]) / "plan.json", plan)
    print(f"{len(sets)} sets x {len(plan['seeds'])} seeds = {len(sets) * len(plan['seeds'])} lineages")
    for strat in sorted(by_strat):
        print(f"  {strat:<12} {[b for b in sets if plan['strategies'][b] == strat]}")


def gen(cfg, plan, h, args):
    from vllm.lora.request import LoRARequest
    from rsi.rollout import make_llm, run_episodes

    todo = [(b, s) for b, s in lineages(plan)
            if not (Path(cfg["run_dir"]) / f"round{h}" / lname(b, s) / "selected.jsonl").exists()]
    if not todo:
        print("nothing to generate")
        return
    if args.compile:
        cfg["vllm"]["enforce_eager"] = False
    items = read_jsonl(Path(cfg["data_dir"]) / "pool.jsonl")[:plan["gen_questions"]]
    r, K = cfg["rollout"], cfg["batches"]["K"]
    llm = make_llm(cfg, enable_lora=True)
    for i, (b, s) in enumerate(todo):
        parent = adapter_dir(cfg, plan, h - 1, b, s)
        trajs = run_episodes(llm, items, n_samples=r["n_samples"], temperature=r["temperature"],
                             top_p=r["top_p"], max_new_tokens=r["max_new_tokens"], max_turns=r["max_turns"],
                             lora_request=LoRARequest(f"r{h}-{lname(b, s)}", i + 1, str(parent)),
                             exec_timeout=r["exec_timeout"], workers=r["workers"],
                             schema_max_chars=r["schema_max_chars"], seed=r["seed"] + 1000 * h + s)
        sel = build_batches(trajs, {plan["rule"]: 1}, K, seed=s)[0]
        by_id = {t["traj_id"]: t for t in trajs}
        out = Path(cfg["run_dir"]) / f"round{h}" / lname(b, s)
        n = len(trajs)
        write_json(out / "stats.json", {
            "parent": str(parent), "n": n, "correct": sum(t["correct"] for t in trajs) / n,
            "safe_all": sum(t["safe_all"] for t in trajs) / n,
            "questions_solved": len({t["qid"] for t in trajs if t["correct"]}) / len(items),
            "selection": {"rule": plan["rule"], "covariates": sel["covariates"],
                          "preferred_frac": sel["preferred_frac"]}})
        # only the selected trajectories are kept: full rollouts would exhaust the disk quota
        write_jsonl(out / "selected.jsonl", [by_id[t] for t in sel["traj_ids"]])
        print(f"gen r{h} {lname(b, s)}: correct={sum(t['correct'] for t in trajs) / n:.3f}", flush=True)


def train(cfg, plan, h):
    from rsi.train import train_lora

    for b, s in lineages(plan):
        out = adapter_dir(cfg, plan, h, b, s)
        if (out / "adapter_config.json").exists():
            continue
        sel = Path(cfg["run_dir"]) / f"round{h}" / lname(b, s) / "selected.jsonl"
        if not sel.exists():
            print(f"skip {lname(b, s)}: no selection yet (run gen --round {h})")
            continue
        convs = [t["messages"] for t in read_jsonl(sel)]
        meta = train_lora(cfg["model"], convs, out, s, cfg["train"],
                          init_adapter=str(adapter_dir(cfg, plan, h - 1, b, s)))
        print(f"train r{h} {lname(b, s)}: loss={meta['train_loss']:.4f}", flush=True)


def evaluate(cfg, plan, h, args):
    from vllm.lora.request import LoRARequest
    from rsi.rollout import make_llm, run_episodes

    k = plan["eval_k"]
    out_dir = Path(cfg["run_dir"]) / f"eval_k{k}" / cfg["eval"]["split"]
    todo = [(b, s) for b, s in lineages(plan)
            if (adapter_dir(cfg, plan, h, b, s) / "adapter_config.json").exists()
            and not (out_dir / f"r{h}__{lname(b, s)}.json").exists()]
    if not todo:
        print("nothing to evaluate")
        return
    if args.compile:
        cfg["vllm"]["enforce_eager"] = False
    items = read_jsonl(Path(cfg["data_dir"]) / f"{cfg['eval']['split']}.jsonl")
    r, e = cfg["rollout"], cfg["eval"]
    llm = make_llm(cfg, enable_lora=True)
    for i, (b, s) in enumerate(todo):
        path = adapter_dir(cfg, plan, h, b, s)
        # same sampling seed as Phase 1's k-sample evaluation (common random numbers)
        trajs = run_episodes(llm, items, n_samples=k, temperature=0.8, top_p=1.0,
                             max_new_tokens=e["max_new_tokens"], max_turns=e["max_turns"],
                             lora_request=LoRARequest(f"e{h}-{lname(b, s)}", i + 1, str(path)),
                             exec_timeout=r["exec_timeout"], workers=r["workers"],
                             schema_max_chars=r["schema_max_chars"], seed=r["seed"])
        hits = defaultdict(list)
        for t in trajs:
            hits[t["qid"]].append(int(t["correct"]))
        correct = {q: sum(v) / len(v) for q, v in hits.items()}
        acc = sum(correct.values()) / len(correct)
        write_json(out_dir / f"r{h}__{lname(b, s)}.json", {
            "name": f"r{h}__{lname(b, s)}", "round": h, "set": b, "seed": s, "samples": k,
            "acc": acc, "n": len(correct), "correct": correct})
        print(f"eval r{h} {lname(b, s)}: pass={acc:.4f}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["plan", "gen", "train", "eval"])
    ap.add_argument("--config", default="configs/phase3.yaml")
    ap.add_argument("--round", type=int, default=2)
    ap.add_argument("--compile", action="store_true", help="vLLM with CUDA graphs (gen/eval)")
    args = ap.parse_args()
    cfg = load_config(args.config)
    if args.stage == "plan":
        return make_plan(cfg)
    plan = read_json(Path(cfg["run_dir"]) / "plan.json")
    if not 2 <= args.round <= plan["horizon"]:
        raise SystemExit(f"--round must be in 2..{plan['horizon']} (round 1 is Phase 1)")
    {"gen": lambda: gen(cfg, plan, args.round, args), "train": lambda: train(cfg, plan, args.round),
     "eval": lambda: evaluate(cfg, plan, args.round, args)}[args.stage]()


if __name__ == "__main__":
    main()
