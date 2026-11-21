"""Environment self-check: versions, GPU, and assistant-only label masking with the
real tokenizer (downloads only the tokenizer, not the weights).

python scripts/check_env.py --config configs/default.yaml
"""
import argparse
import sys

from rsi.train import build_example
from rsi.utils import load_config


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    cfg = load_config(ap.parse_args().config)

    import peft
    import torch
    import transformers
    import vllm
    from transformers import AutoTokenizer

    print(f"python {sys.version.split()[0]} | torch {torch.__version__} | transformers "
          f"{transformers.__version__} | peft {peft.__version__} | vllm {vllm.__version__}")
    print(f"cuda available: {torch.cuda.is_available()}",
          f"| {torch.cuda.get_device_name(0)}" if torch.cuda.is_available() else "")

    tok = AutoTokenizer.from_pretrained(cfg["model"])
    msgs = [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "Q1"},
        {"role": "assistant", "content": "```sql\nSELECT 1\n```"},
        {"role": "user", "content": "Execution failed: E"},
        {"role": "assistant", "content": "```sql\nSELECT 2\n```"},
    ]
    ex = build_example(tok, msgs, max_len=4096, chat_kwargs=cfg.get("chat_template_kwargs"))
    if ex is None:
        sys.exit("FAIL: chat template is not prefix-consistent; label masking would be wrong")
    trained = tok.decode([t for t in ex["labels"] if t != -100])
    print(f"trained-on text: {trained!r}")
    ok = "SELECT 1" in trained and "SELECT 2" in trained and "Q1" not in trained \
        and "SYS" not in trained and "Execution failed" not in trained
    print("label masking: OK" if ok else "label masking: FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
