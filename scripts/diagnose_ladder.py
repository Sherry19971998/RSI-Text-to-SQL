"""X1/X2: feedback-ladder diagnosis of execution-feedback self-correction (inference only).

One greedy initial SQL per question is generated once and shared by every level, so levels
differ only in the feedback they give (see rsi.ladder). Resumable: finished levels are
skipped. Output: {run_dir}/initial.jsonl, level_{name}.jsonl, summary.json.

python scripts/diagnose_ladder.py --config configs/diagnose.yaml --limit 50     # smoke test
python scripts/diagnose_ladder.py --config configs/diagnose.yaml --compile
python scripts/diagnose_ladder.py --config configs/diagnose_qwen3.yaml --levels r1 exec
"""
import argparse
import sqlite3
from pathlib import Path

from rsi.ladder import LEVELS, run_level, summarize
from rsi.prompts import extract_sql, initial_messages
from rsi.utils import load_config, read_jsonl, write_json, write_jsonl


def gold_n_cols(db_path, sql, timeout=60.0):
    import time
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    deadline = time.monotonic() + timeout
    conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
    try:
        cur = conn.execute(sql)
        return len(cur.description or [])
    except sqlite3.Error:
        return None
    finally:
        conn.close()


def make_generate(llm, max_new_tokens, chat_kwargs):
    from vllm import SamplingParams
    params = SamplingParams(temperature=0.0, top_p=1.0, max_tokens=max_new_tokens)

    def generate(prompts):
        outs = llm.chat(prompts, params, use_tqdm=True,
                        **({"chat_template_kwargs": chat_kwargs} if chat_kwargs else {}))
        return [(o.outputs[0].text, len(o.outputs[0].token_ids), len(o.prompt_token_ids)) for o in outs]
    return generate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/diagnose.yaml")
    ap.add_argument("--levels", nargs="+", default=None, help=f"subset of {LEVELS}")
    ap.add_argument("--limit", type=int, default=None, help="first N questions, separate run dir")
    ap.add_argument("--compile", action="store_true", help="vllm.enforce_eager=false")
    args = ap.parse_args()
    cfg = load_config(args.config)
    if args.compile:
        cfg["vllm"]["enforce_eager"] = False
    d = cfg["diag"]
    levels = args.levels or d["levels"]
    run_dir = Path(cfg["run_dir"]) / (f"smoke{args.limit}" if args.limit else "full")
    items = read_jsonl(d["test_file"])[:args.limit]
    items = [it for it in items if it.get("gold_hash")]
    todo = [lv for lv in levels if not (run_dir / f"level_{lv}.jsonl").exists()]
    if "oracle_shape" in todo:
        for it in items:
            it.setdefault("gold_n_cols", gold_n_cols(it["db_path"], it["gold_sql"]))
    init_path = run_dir / "initial.jsonl"
    if not todo and init_path.exists():
        print("nothing to run")
    else:
        from rsi.rollout import make_llm
        llm = make_llm(cfg, enable_lora=False)
        generate = make_generate(llm, d["max_new_tokens"], cfg.get("chat_template_kwargs"))
        if init_path.exists():
            initial = read_jsonl(init_path)
        else:
            msgs = [initial_messages(it, cfg["rollout"]["schema_max_chars"]) for it in items]
            gens = generate(msgs)
            initial = [{"qid": it["qid"], "sql": extract_sql(t),
                        "messages": m + [{"role": "assistant", "content": t}],
                        "out_tokens": n_out, "in_tokens": n_in}
                       for it, m, (t, n_out, n_in) in zip(items, msgs, gens)]
            write_jsonl(init_path, initial)
        by_q = {x["qid"]: x for x in initial}
        initial = [by_q[it["qid"]] for it in items]
        for lv in todo:
            recs = run_level(generate, items, initial, lv, rounds=d["rounds"],
                             exec_timeout=cfg["rollout"]["exec_timeout"],
                             workers=cfg["rollout"]["workers"], n_preview=d["n_preview"])
            write_jsonl(run_dir / f"level_{lv}.jsonl", recs)
            print(lv, summarize(recs, d["rounds"])["rounds"][-1])

    summary = {}
    diff = {it["qid"]: it.get("difficulty") for it in items}
    for lv in LEVELS:
        p = run_dir / f"level_{lv}.jsonl"
        if not p.exists():
            continue
        recs = read_jsonl(p)
        summary[lv] = summarize(recs, d["rounds"])
        summary[lv]["by_difficulty"] = {
            k: summarize([r for r in recs if diff.get(r["qid"]) == k], d["rounds"])["rounds"][-1]
            for k in sorted({v for v in diff.values() if v})}
        loc = [h["loc"] for r in recs for h in r["history"][:1] if "loc" in h]
        if loc:
            from collections import Counter
            summary[lv]["round1_loc_basis"] = dict(Counter(x["fix_basis"] for x in loc))
            summary[lv]["round1_fix_slots"] = dict(Counter(s for x in loc if x["fix_basis"] == "single"
                                                           for s in x["fix_slots"]))
    write_json(run_dir / "summary.json", {"model": cfg["model"], "n": len(items), "levels": summary})
    print(f"\n{'level':14s} {'init':>6s} {'final':>6s} {'w->c':>6s} {'c->w':>6s} {'net':>6s} {'calls':>6s}")
    for lv, s in summary.items():
        f = s["rounds"][-1]
        print(f"{lv:14s} {s['init_acc']*100:6.2f} {f['acc']*100:6.2f} {f['w2c_rate']*100:6.2f} "
              f"{f['c2w_rate']*100:6.2f} {f['net']*100:+6.2f} {s['calls']:6d}")


if __name__ == "__main__":
    main()
