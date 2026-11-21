"""Continuous utility metric: per-question NLL of the gold SQL under theta_0 and every adapter.

Greedy 0/1 accuracy on a fixed question set is dominated by borderline questions that flip
under any small update (see robustness.py). Teacher-forced NLL of the gold answer is
continuous and does not flip, so batch effects can be measured with far less noise.

For each question the assistant turn is "```sql\\n<gold SQL>\\n```" and the score is the mean
NLL over the gold SQL tokens only. The code-fence tokens are context, not targets: adapters
are trained on reason-then-SQL trajectories, so scoring the opening fence would mostly measure
a format shift rather than SQL quality. One forward
pass per question; LoRA adapters are hot-swapped on a single base model. Resumable.

python scripts/evaluate_nll.py --config configs/default.yaml
"""
import argparse
import time
from pathlib import Path

from rsi.prompts import initial_messages
from rsi.utils import load_config, read_jsonl, write_json


def build_sql_only(tok, msgs, gold, max_len):
    """input_ids for the chat; labels only on tokens inside the gold SQL span."""
    text = tok.apply_chat_template(msgs, tokenize=False)
    start = text.rfind("```sql\n" + gold)
    if start < 0:
        return None
    start += len("```sql\n")
    end = start + len(gold)
    enc = tok(text, add_special_tokens=False, return_offsets_mapping=True)
    ids = list(enc["input_ids"])
    if len(ids) > max_len:
        return None
    labels = [t if (a >= start and a < end) else -100 for t, (a, b) in zip(ids, enc["offset_mapping"])]
    if all(l == -100 for l in labels):
        return None
    return {"input_ids": ids, "labels": labels}


def score_all(core, lm_head, feats, batch_size, device):
    """Mean NLL over label tokens for each example. Only label positions go through lm_head,
    which avoids materializing full-vocabulary logits for the long schema prompt."""
    import torch
    import torch.nn.functional as F

    order = sorted(range(len(feats)), key=lambda i: len(feats[i]["input_ids"]))
    out = [None] * len(feats)
    for s in range(0, len(order), batch_size):
        idx = order[s:s + batch_size]
        L = max(len(feats[i]["input_ids"]) for i in idx)
        ids = torch.zeros(len(idx), L, dtype=torch.long)
        att = torch.zeros(len(idx), L, dtype=torch.long)
        for r, i in enumerate(idx):
            n = len(feats[i]["input_ids"])
            ids[r, :n] = torch.tensor(feats[i]["input_ids"])
            att[r, :n] = 1
        with torch.no_grad():
            h = core(input_ids=ids.to(device), attention_mask=att.to(device)).last_hidden_state
            for r, i in enumerate(idx):
                lab = feats[i]["labels"]
                pos = [t for t in range(len(lab) - 1) if lab[t + 1] != -100]
                tgt = torch.tensor([lab[t + 1] for t in pos], device=device)
                logits = lm_head(h[r, pos]).float()
                out[i] = F.cross_entropy(logits, tgt, reduction="mean").item()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--split", default=None, help="default: eval.split from config")
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--limit", type=int, default=None, help="smoke test: first N questions, first 2 adapters")
    args = ap.parse_args()
    cfg = load_config(args.config)
    split = args.split or cfg["eval"]["split"]
    run_dir = Path(cfg["run_dir"])
    # smoke-test results go elsewhere so a later full run does not skip them as done
    out_dir = run_dir / ("nll_smoke" if args.limit else "nll") / split
    items = read_jsonl(Path(cfg["data_dir"]) / f"{split}.jsonl")[:args.limit]

    adapters = sorted(p for p in (run_dir / "adapters").glob("*") if (p / "adapter_config.json").exists())
    if args.limit:
        adapters = adapters[:2]
    todo = [p for p in adapters if args.limit or not (out_dir / f"{p.name}.json").exists()]
    need_base = bool(args.limit) or not (out_dir / "base.json").exists()
    if not todo and not need_base:
        print("nothing to evaluate")
        return

    import torch
    import transformers
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(cfg["model"])
    smc = cfg["rollout"]["schema_max_chars"]
    feats, qids = [], []
    for it in items:
        msgs = initial_messages(it, smc) + [{"role": "assistant", "content": f"```sql\n{it['gold_sql']}\n```"}]
        f = build_sql_only(tok, msgs, it["gold_sql"], cfg["train"]["max_len"])
        if f is not None:
            feats.append(f)
            qids.append(it["qid"])
    print(f"{len(feats)}/{len(items)} questions scorable; {len(todo)} adapters to score; base needed: {need_base}")

    major, minor = (int(x) for x in transformers.__version__.split(".")[:2])
    dtype_kw = "dtype" if (major, minor) >= (4, 56) else "torch_dtype"
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = AutoModelForCausalLM.from_pretrained(cfg["model"], attn_implementation="sdpa",
                                                 **{dtype_kw: torch.bfloat16}).to(device).eval()

    def save(name, nll):
        write_json(out_dir / f"{name}.json", {
            "name": name, "split": split, "metric": "gold_sql_body_mean_token_nll",
            "mean_nll": sum(nll) / len(nll), "n": len(nll), "nll": dict(zip(qids, nll))})

    if need_base:
        t0 = time.time()
        nll = score_all(model.model, model.lm_head, feats, args.batch_size, device)
        save("base", nll)
        print(f"base: mean NLL={sum(nll) / len(nll):.4f} ({time.time() - t0:.0f}s)")

    peft_model, prev = None, None
    for p in todo:
        t0 = time.time()
        if peft_model is None:
            peft_model = PeftModel.from_pretrained(model, str(p), adapter_name=p.name)
        else:
            peft_model.load_adapter(str(p), adapter_name=p.name)
        peft_model.set_adapter(p.name)
        peft_model.eval()
        base = peft_model.get_base_model()  # LoRA layers are injected in place, so they are active
        nll = score_all(base.model, base.lm_head, feats, args.batch_size, device)
        save(p.name, nll)
        if prev is not None:  # keep at most two adapters loaded; never delete the active one
            peft_model.delete_adapter(prev)
        prev = p.name
        print(f"{p.name}: mean NLL={sum(nll) / len(nll):.4f} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
