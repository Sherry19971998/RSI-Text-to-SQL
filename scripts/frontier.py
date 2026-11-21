"""Frontier experiment pipeline. A lineage = (selection rule, seed), starting from theta_0.

Round h:
  gen    the lineage's theta_{h-1} samples every pool question first_samples times, then tops up
         questions with few successes to first+topup samples; the rule selects K trajectories.
         Round 1 generation (theta_0) is shared by all rules of the same seed: identical data,
         different selections. Only the selection and compact per-question stats are stored.
  train  continue the lineage's LoRA (round 1: fresh LoRA) on its selection -> theta_h
  eval   sampled pass rate (k per question) on util-val
Stages are separate processes; each is resumable.

python scripts/frontier.py gen   --config configs/frontier.yaml --round 1 --compile
python scripts/frontier.py train --config configs/frontier.yaml --round 1
python scripts/frontier.py eval  --config configs/frontier.yaml --round 1 --compile
(or: bash scripts/run_frontier.sh --compile)
"""
import argparse
from collections import defaultdict
from pathlib import Path

from rsi.frontier import question_stats, select
from rsi.utils import load_config, read_json, read_jsonl, write_json, write_jsonl


def active(cfg, rule, h):
    """A rule runs round h only if h <= its horizon (frontier.rule_horizon overrides horizon)."""
    fr = cfg["frontier"]
    return h <= fr.get("rule_horizon", {}).get(rule, fr["horizon"])


def lname(rule, s):
    return f"{rule}__s{s}"


def ldir(cfg, h, rule, s):
    # frontier.round1_alias: a rule whose round-1 selection is identical to another rule's reuses
    # that lineage's round-1 selection, solved set and adapter instead of training a copy
    if h == 1:
        rule = cfg["frontier"].get("round1_alias", {}).get(rule, rule)
    return Path(cfg["run_dir"]) / f"round{h}" / lname(rule, s)


def adapter(cfg, h, rule, s):
    return ldir(cfg, h, rule, s) / "adapter"


def solved_before(cfg, h, rule, s):
    """qids this lineage solved (>= 1 correct sample) in any round before h."""
    out = set()
    for hh in range(1, h):
        f = ldir(cfg, hh, rule, s) / "solved.json"
        if f.exists():
            out |= set(read_json(f))
    return out


def pass_history(cfg, h, rule, s):
    """qid -> pass rates on the pool in rounds 1..h-1 of this lineage (for the cartography rule)."""
    hist = defaultdict(list)
    for hh in range(1, h):
        f = ldir(cfg, hh, rule, s) / "qstats.json"
        if f.exists():
            for q, (c, n) in read_json(f).items():
                hist[q].append(c / n)
    return dict(hist)


def generate(llm, cfg, items, lora, seed):
    from rsi.rollout import run_episodes

    fr, r = cfg["frontier"], cfg["rollout"]
    kw = dict(temperature=r["temperature"], top_p=r["top_p"], max_new_tokens=r["max_new_tokens"],
              max_turns=r["max_turns"], lora_request=lora, exec_timeout=r["exec_timeout"],
              workers=r["workers"], schema_max_chars=r["schema_max_chars"])
    first = run_episodes(llm, items, n_samples=fr["first_samples"], seed=seed, **kw)
    st = question_stats(first)
    weak = [it for it in items if st[it["qid"]][0] <= fr["topup_max_correct"]]
    extra = run_episodes(llm, weak, n_samples=fr["topup_samples"], seed=seed + 500, **kw) if weak else []
    for t in extra:  # distinct ids from the first pass
        t["traj_id"] = f"{t['qid']}#t{t['sample_idx']}"
    return first, extra


def distinct_correct(trajs):
    """qid -> number of distinct correct final SQL strings (case/whitespace-normalised)."""
    out = defaultdict(set)
    for t in trajs:
        if t["correct"]:
            out[t["qid"]].add(" ".join(t["final_sql"].lower().split()).rstrip(";").strip())
    return {q: len(v) for q, v in out.items()}


def save_selection(cfg, h, rule, s, first, extra, parent, prev):
    fr, K = cfg["frontier"], cfg["batches"]["K"]
    if rule == "frontier_no_topup":  # ablation: select from the first 8 samples only
        extra = []
    trajs = first + extra
    qst = question_stats(trajs)
    # "<rule>_restart" selects like <rule> but trains each round from the base model (STaR / ReST-EM)
    ids, summ = select(rule.removesuffix("_restart"), trajs, qst, prev, K, seed=s, rare_rate=fr["rare_rate"],
                       max_per_question=fr["max_per_question"], history=pass_history(cfg, h, rule, s))
    by = {t["traj_id"]: t for t in trajs}
    st8 = question_stats(first)
    solved = sorted(q for q, (c, n) in qst.items() if c > 0)
    n_q = len(st8)
    out = ldir(cfg, h, rule, s)
    write_json(out / "solved.json", solved)
    write_json(out / "qstats.json", qst)
    dc8, dc = distinct_correct(first), distinct_correct(trajs)
    write_json(out / "distinct.json", dc)
    write_json(out / "stats.json", {
        "rule": rule, "seed": s, "round": h, "parent": parent, "n_questions": n_q,
        "per_sample_correct_first_pass": sum(c for c, n in st8.values()) / sum(n for c, n in st8.values()),
        "solved_frac_first_pass": sum(c > 0 for c, n in st8.values()) / n_q,
        "solved_frac_with_topup": len(solved) / n_q,
        "n_topup_questions": len({t["qid"] for t in extra}),
        "n_newly_solved": len(set(solved) - prev) if prev else None,
        "distinct_correct_sql_first_pass": sum(dc8.values()) / max(len(dc8), 1),  # per solved question
        "distinct_correct_sql_with_topup": sum(dc.values()) / max(len(dc), 1),
        "selection": summ})
    write_jsonl(out / "selected.jsonl", [by[i] for i in ids])
    print(f"gen r{h} {lname(rule, s)}: solved8={sum(c > 0 for c, n in st8.values()) / n_q:.3f} "
          f"solved32={len(solved) / n_q:.3f} rare_q={summ['n_rare_q']} newly={summ['n_newly_solved_q']}",
          flush=True)


def gen(cfg, h, args):
    from vllm.lora.request import LoRARequest
    from rsi.rollout import make_llm

    fr = cfg["frontier"]
    done = lambda rule, s: (not active(cfg, rule, h)) or (ldir(cfg, h, rule, s) / "selected.jsonl").exists()
    if all(done(rule, s) for rule in fr["rules"] for s in fr["seeds"]):
        print("nothing to generate")
        return
    if args.compile:
        cfg["vllm"]["enforce_eager"] = False
    items = read_jsonl(Path(cfg["data_dir"]) / "pool.jsonl")[:fr["gen_questions"]]
    llm = make_llm(cfg, enable_lora=True)
    base_seed = cfg["rollout"]["seed"]
    if h == 1:  # theta_0 data is shared by every rule of a seed
        for s in fr["seeds"]:
            if all(done(rule, s) for rule in fr["rules"]):
                continue
            first, extra = generate(llm, cfg, items, None, base_seed + 1000 + s)
            for rule in fr["rules"]:
                if not done(rule, s):
                    save_selection(cfg, 1, rule, s, first, extra, "theta_0", set())
        return
    lid = 0
    for rule in fr["rules"]:
        for s in fr["seeds"]:
            if done(rule, s):
                continue
            parent = adapter(cfg, h - 1, rule, s)
            if not (parent / "adapter_config.json").exists():
                print(f"skip {lname(rule, s)}: round {h - 1} adapter missing")
                continue
            lid += 1
            # same sampling seed for every rule (common random numbers)
            first, extra = generate(llm, cfg, items, LoRARequest(f"g{h}-{lname(rule, s)}", lid, str(parent)),
                                    base_seed + 1000 * h + s)
            save_selection(cfg, h, rule, s, first, extra, str(parent), solved_before(cfg, h, rule, s))


def train(cfg, h):
    from rsi.train import train_lora

    fr = cfg["frontier"]
    for rule in fr["rules"]:
        if not active(cfg, rule, h):
            continue
        for s in fr["seeds"]:
            out = adapter(cfg, h, rule, s)
            sel = ldir(cfg, h, rule, s) / "selected.jsonl"
            if (out / "adapter_config.json").exists() or not sel.exists():
                continue
            restart = h == 1 or rule.endswith("_restart")   # fresh LoRA on the base model
            init = None if restart else str(adapter(cfg, h - 1, rule, s))
            tcfg = {**cfg["train"], "chat_template_kwargs": cfg.get("chat_template_kwargs")}
            meta = train_lora(cfg["model"], [t["messages"] for t in read_jsonl(sel)], out, s,
                              tcfg, init_adapter=init)
            print(f"train r{h} {lname(rule, s)}: loss={meta['train_loss']:.4f}", flush=True)


def eval_one(llm, cfg, items, lora, k):
    from rsi.rollout import run_episodes

    r, e = cfg["rollout"], cfg["eval"]
    # same sampling seed as every other k-sample evaluation (common random numbers)
    trajs = run_episodes(llm, items, n_samples=k, temperature=0.8, top_p=1.0,
                         max_new_tokens=e["max_new_tokens"], max_turns=e["max_turns"], lora_request=lora,
                         exec_timeout=r["exec_timeout"], workers=r["workers"],
                         schema_max_chars=r["schema_max_chars"], seed=r["seed"])
    hits = defaultdict(list)
    for t in trajs:
        hits[t["qid"]].append(int(t["correct"]))
    correct = {q: sum(v) / len(v) for q, v in hits.items()}
    return correct, sum(correct.values()) / len(correct), sum(v > 0 for v in correct.values()) / len(correct)


def evaluate(cfg, h, args):
    from vllm.lora.request import LoRARequest
    from rsi.rollout import make_llm

    fr = cfg["frontier"]
    k, split = fr["eval_k"], args.split or cfg["eval"]["split"]
    out_dir = Path(cfg["run_dir"]) / f"eval_k{k}" / split
    # theta_0 on this split, unless util-val reuses an existing evaluation (frontier.base_eval)
    reuse = split == cfg["eval"]["split"] and fr.get("base_eval")
    need_base = not reuse and not (out_dir / "base.json").exists()
    todo = [(rule, s) for rule in fr["rules"] for s in fr["seeds"]
            if (adapter(cfg, h, rule, s) / "adapter_config.json").exists()
            and not (out_dir / f"r{h}__{lname(rule, s)}.json").exists()]
    if not todo and not need_base:
        print("nothing to evaluate")
        return
    if args.compile:
        cfg["vllm"]["enforce_eager"] = False
    items = read_jsonl(Path(cfg["data_dir"]) / f"{split}.jsonl")[:fr.get("eval_limit")]
    llm = make_llm(cfg, enable_lora=True)
    if need_base:
        correct, acc, cov = eval_one(llm, cfg, items, None, k)
        write_json(out_dir / "base.json", {"round": 0, "split": split, "samples": k, "acc": acc,
                                           "coverage": cov, "n": len(correct), "correct": correct})
        print(f"eval {split} base: pass={acc:.4f} coverage={cov:.4f}", flush=True)
    for i, (rule, s) in enumerate(todo):
        lora = LoRARequest(f"e{h}-{lname(rule, s)}", i + 1, str(adapter(cfg, h, rule, s)))
        correct, acc, cov = eval_one(llm, cfg, items, lora, k)
        write_json(out_dir / f"r{h}__{lname(rule, s)}.json", {
            "round": h, "rule": rule, "seed": s, "split": split, "samples": k, "acc": acc,
            "coverage": cov, "n": len(correct), "correct": correct})
        print(f"eval r{h} {split} {lname(rule, s)}: pass={acc:.4f} coverage={cov:.4f}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["gen", "train", "eval"])
    ap.add_argument("--config", default="configs/frontier.yaml")
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--compile", action="store_true", help="vLLM with CUDA graphs (gen/eval)")
    ap.add_argument("--split", default=None, help="eval only: e.g. test (BIRD dev); default eval.split")
    args = ap.parse_args()
    cfg = load_config(args.config)
    if not 1 <= args.round <= cfg["frontier"]["horizon"]:
        raise SystemExit(f"--round must be in 1..{cfg['frontier']['horizon']}")
    {"gen": lambda: gen(cfg, args.round, args), "train": lambda: train(cfg, args.round),
     "eval": lambda: evaluate(cfg, args.round, args)}[args.stage]()


if __name__ == "__main__":
    main()
