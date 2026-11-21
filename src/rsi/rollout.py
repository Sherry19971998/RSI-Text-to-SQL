"""Stage 1: self-generated multi-turn Text-to-SQL rollouts with vLLM.

Protocol per episode (deterministic given model outputs):
  turn k: model writes SQL -> static check -> sandboxed execution
          non-empty result         -> episode ends, this SQL is final
          error / empty / blocked  -> feedback message, model repairs (up to max_turns)
"""
from __future__ import annotations

from .prompts import extract_sql, feedback_message, initial_messages, schema_columns
from .sandbox import check_dict, check_sql, execute_many


def run_episodes(llm, items, *, n_samples=1, temperature=0.0, top_p=1.0, max_new_tokens=512,
                 max_turns=3, lora_request=None, exec_timeout=10.0, workers=8, max_rows=100_000,
                 schema_max_chars=12000, seed=0) -> list[dict]:
    from vllm import SamplingParams

    episodes = []
    for it in items:
        for k in range(n_samples):
            episodes.append({"item": it, "k": k, "turns": [],
                             "messages": initial_messages(it, schema_max_chars)})

    active = list(range(len(episodes)))
    for turn in range(max_turns):
        if not active:
            break
        params = [SamplingParams(temperature=temperature, top_p=top_p, max_tokens=max_new_tokens,
                                 seed=None if temperature == 0 else seed * 1_000_003 + i * 97 + turn)
                  for i in active]
        kw = getattr(llm, "rsi_chat_kwargs", None)  # e.g. {"enable_thinking": False} for Qwen3
        outs = llm.chat([episodes[i]["messages"] for i in active], params,
                        lora_request=lora_request, use_tqdm=True,
                        **({"chat_template_kwargs": kw} if kw else {}))
        texts = [o.outputs[0].text for o in outs]
        n_toks = [len(o.outputs[0].token_ids) for o in outs]
        sqls = [extract_sql(t) for t in texts]
        checks = [check_sql(s, schema_columns(episodes[i]["item"]["db_path"]))
                  for i, s in zip(active, sqls)]
        results = execute_many(
            [(episodes[i]["item"]["db_path"], s if c.safe else None)
             for i, s, c in zip(active, sqls, checks)],
            timeout=exec_timeout, workers=workers, max_rows=max_rows)

        still = []
        for i, text, nt, sql, c, r in zip(active, texts, n_toks, sqls, checks, results):
            ep = episodes[i]
            if not c.safe:
                r = {**r, "error": f"blocked: {c.reason}" if sql else "no SQL found in response"}
            ep["messages"].append({"role": "assistant", "content": text})
            ep["turns"].append({"sql": sql, "check": check_dict(c), "out_tokens": nt,
                                **{k: r[k] for k in ("ok", "error", "n_rows", "truncated", "hash", "time")}})
            if (r["ok"] and r["n_rows"] > 0) or turn == max_turns - 1:
                continue
            ep["messages"].append({"role": "user", "content": feedback_message(r)})
            still.append(i)
        active = still

    return [_finalize(ep) for ep in episodes]


def _finalize(ep) -> dict:
    it, turns = ep["item"], ep["turns"]
    last = turns[-1]
    # Drop a trailing feedback message (cannot happen with current protocol, but keep
    # stored trajectories ending on the assistant turn).
    msgs = ep["messages"]
    while msgs and msgs[-1]["role"] != "assistant":
        msgs = msgs[:-1]
    n_failed = sum(not t["ok"] for t in turns)
    correct = bool(last["ok"] and not last["truncated"] and last["hash"] == it["gold_hash"])
    return {
        "traj_id": f"{it['qid']}#{ep['k']}",
        "qid": it["qid"],
        "db_id": it["db_id"],
        "sample_idx": ep["k"],
        "messages": msgs,
        "turns": turns,
        "final_sql": last["sql"],
        "correct": correct,
        "n_turns": len(turns),
        "n_failed_exec": n_failed,
        "n_empty": sum(t["ok"] and t["n_rows"] == 0 for t in turns),
        "recovered": n_failed > 0 and last["ok"],
        "safe_all": all(t["check"]["safe"] for t in turns),
        "schema_ok_all": all(t["check"]["schema_ok"] for t in turns),
        "repeated_sql": len(turns) - len({t["sql"] for t in turns}),
        "n_out_tokens": sum(t["out_tokens"] for t in turns),
    }


def make_llm(cfg: dict, enable_lora: bool):
    import os
    v = cfg["vllm"]
    # FlashInfer's sampler JIT-compiles CUDA kernels and needs nvcc, which machines with
    # only the driver installed lack. Must be set before vLLM starts its engine process.
    if not v.get("flashinfer_sampler", False):
        os.environ["VLLM_USE_FLASHINFER_SAMPLER"] = "0"
    from vllm import LLM
    llm = LLM(model=cfg["model"], enable_lora=enable_lora, max_lora_rank=v["max_lora_rank"],
               max_loras=1, max_model_len=cfg["rollout"]["max_model_len"],
               gpu_memory_utilization=v["gpu_memory_utilization"],
               tensor_parallel_size=v["tensor_parallel_size"], seed=cfg["rollout"]["seed"],
               enforce_eager=v.get("enforce_eager", False))
    llm.rsi_chat_kwargs = cfg.get("chat_template_kwargs")
    return llm
