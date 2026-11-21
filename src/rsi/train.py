"""Short LoRA SFT update on a rollout set B (loss on assistant turns only)."""
from __future__ import annotations

import json
import math
from pathlib import Path


def _chat_ids(tokenizer, messages, add_generation_prompt=False, chat_kwargs=None) -> list:
    # transformers 5.x returns a dict from apply_chat_template unless return_dict=False.
    out = tokenizer.apply_chat_template(messages, tokenize=True, return_dict=False,
                                        add_generation_prompt=add_generation_prompt, **(chat_kwargs or {}))
    if isinstance(out, dict) or hasattr(out, "keys"):
        out = out["input_ids"]
    return list(out)


END_OF_TURN = ("<|im_end|>", "<|eot_id|>", "<end_of_turn>", "</s>")


def _build_by_offsets(tokenizer, messages, max_len, chat_kwargs=None):
    """Template-agnostic fallback: render the conversation once, locate each assistant message's
    text (plus its end-of-turn marker) by character offsets, and label only those tokens."""
    text = tokenizer.apply_chat_template(messages, tokenize=False, **(chat_kwargs or {}))
    spans, cursor = [], 0
    for m in messages:
        if m["role"] != "assistant":
            continue
        start = text.find(m["content"], cursor)
        if start < 0:
            return None
        end = start + len(m["content"])
        rest = text[end:]
        for marker in END_OF_TURN:  # the model must learn to stop
            if rest.lstrip(" \n").startswith(marker):
                end += (len(rest) - len(rest.lstrip(" \n"))) + len(marker)
                break
        spans.append((start, end))
        cursor = end
    enc = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
    ids = list(enc["input_ids"])
    if len(ids) > max_len:
        return None
    labels = [t if any(a <= lo < b for a, b in spans) else -100
              for t, (lo, hi) in zip(ids, enc["offset_mapping"])]
    return {"input_ids": ids, "labels": labels}


def build_example(tokenizer, messages, max_len, chat_kwargs=None):
    """Tokenize a multi-turn conversation; labels = token ids on assistant turns, -100
    elsewhere. Uses prefix tokenization when the chat template is prefix-consistent (Qwen2.5);
    otherwise (e.g. Qwen3, whose template rewrites earlier turns) falls back to locating the
    assistant text by character offsets. Returns None if the example exceeds max_len."""
    full = _chat_ids(tokenizer, messages, chat_kwargs=chat_kwargs)
    if len(full) > max_len:
        return None
    labels = [-100] * len(full)
    for i, m in enumerate(messages):
        if m["role"] != "assistant":
            continue
        prefix = _chat_ids(tokenizer, messages[:i], add_generation_prompt=True, chat_kwargs=chat_kwargs)
        upto = _chat_ids(tokenizer, messages[:i + 1], chat_kwargs=chat_kwargs)
        if full[:len(upto)] != upto or upto[:len(prefix)] != prefix:
            return _build_by_offsets(tokenizer, messages, max_len, chat_kwargs)
        labels[len(prefix):len(upto)] = full[len(prefix):len(upto)]
    return {"input_ids": full, "labels": labels}


def _divergence_guard(max_loss: float = 20.0):
    """Abort as soon as a logged loss or grad norm is non-finite or absurd, instead of
    silently saving a NaN adapter (an adapter is only saved after training succeeds)."""
    from transformers import TrainerCallback

    class DivergenceGuard(TrainerCallback):
        def on_log(self, args, state, control, logs=None, **kwargs):
            logs = logs or {}
            for k in ("loss", "grad_norm"):
                v = logs.get(k)
                if v is None:
                    continue
                v = float(v)
                if not math.isfinite(v) or (k == "loss" and v > max_loss):
                    raise RuntimeError(f"training diverged at step {state.global_step}: {k}={v}")

    return DivergenceGuard()


def train_lora(model_name, conversations, out_dir, seed, tcfg, init_adapter=None) -> dict:
    import torch
    import transformers
    from peft import LoraConfig, PeftModel, get_peft_model
    from transformers import (AutoModelForCausalLM, AutoTokenizer, Trainer,
                              TrainingArguments, set_seed)

    set_seed(seed)
    tok = AutoTokenizer.from_pretrained(model_name)
    pad_id = tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id
    chat_kwargs = tcfg.get("chat_template_kwargs")
    feats = [build_example(tok, msgs, tcfg["max_len"], chat_kwargs) for msgs in conversations]
    n_dropped = sum(f is None for f in feats)
    feats = [f for f in feats if f is not None]

    def collate(batch):
        L = max(len(b["input_ids"]) for b in batch)
        ids = [b["input_ids"] + [pad_id] * (L - len(b["input_ids"])) for b in batch]
        lab = [b["labels"] + [-100] * (L - len(b["labels"])) for b in batch]
        att = [[1] * len(b["input_ids"]) + [0] * (L - len(b["input_ids"])) for b in batch]
        return {"input_ids": torch.tensor(ids), "labels": torch.tensor(lab),
                "attention_mask": torch.tensor(att)}

    # `torch_dtype` was renamed `dtype` in transformers 4.56; older versions ignore `dtype`.
    major, minor = (int(x) for x in transformers.__version__.split(".")[:2])
    dtype_kw = "dtype" if (major, minor) >= (4, 56) else "torch_dtype"
    model = AutoModelForCausalLM.from_pretrained(model_name, attn_implementation="sdpa",
                                                 **{dtype_kw: torch.bfloat16})
    model.enable_input_require_grads()
    if init_adapter:
        model = PeftModel.from_pretrained(model, init_adapter, is_trainable=True)
    else:
        model = get_peft_model(model, LoraConfig(
            r=tcfg["lora_r"], lora_alpha=tcfg["lora_alpha"], lora_dropout=tcfg["lora_dropout"],
            target_modules=tcfg["target_modules"], task_type="CAUSAL_LM"))

    out_dir = Path(out_dir)
    # Explicit warmup steps: transformers 5.x removed `warmup_ratio`.
    steps_per_epoch = math.ceil(len(feats) / (tcfg["per_device_batch"] * tcfg["grad_accum"]))
    warmup_steps = max(1, round(0.05 * steps_per_epoch * tcfg["epochs"]))
    args = TrainingArguments(
        output_dir=str(out_dir / "_trainer"),
        per_device_train_batch_size=tcfg["per_device_batch"],
        gradient_accumulation_steps=tcfg["grad_accum"],
        num_train_epochs=tcfg["epochs"],
        learning_rate=tcfg["learning_rate"],
        lr_scheduler_type="cosine",
        warmup_steps=warmup_steps,
        bf16=True,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        logging_steps=tcfg.get("logging_steps", 5),
        save_strategy="no",
        report_to=[],
        seed=seed,
        data_seed=seed,
        remove_unused_columns=False,
        logging_nan_inf_filter=False,  # the default hides NaN losses in the logs
    )
    result = Trainer(model=model, args=args, train_dataset=feats, data_collator=collate,
                     callbacks=[_divergence_guard()]).train()
    model.save_pretrained(str(out_dir))
    meta = {
        "seed": seed,
        "n_examples": len(feats),
        "n_dropped": n_dropped,
        "n_tokens": sum(len(f["input_ids"]) for f in feats),
        "n_label_tokens": sum(sum(l != -100 for l in f["labels"]) for f in feats),
        "train_loss": result.training_loss,
        "init_adapter": init_adapter,
    }
    (out_dir / "train_meta.json").write_text(json.dumps(meta, indent=2))
    del model
    torch.cuda.empty_cache()
    return meta
