#!/usr/bin/env bash
# Start a local OpenAI-compatible vLLM server for the task model and improver, with a small,
# explicit GPU memory share. Upstream's own local-vLLM mode hard-codes
# gpu_memory_utilization=0.8 and tensor_parallel_size=<all GPUs> (lse/agents/base.py), which fails
# on a shared GPU; serving the model ourselves and using upstream's API mode avoids editing upstream.
#
# Usage (inside the upstream venv):
#   bash scripts/serve_model.sh            # foreground
#   GPU=0 MEM=0.30 PORT=8011 bash scripts/serve_model.sh
# Then, in the shell that runs experiments:
#   export LSE_MODEL_URL=http://127.0.0.1:8011/v1 OPENAI_API_KEY=EMPTY
#
# Defaults sized for engr-liu01s (1x H100 80 GB, shared): 0.40 x 80 GB ~ 33 GB, leaving ~45 GB for
# other users. vLLM refuses to start if that exceeds the currently free memory; check `nvidia-smi`.
#
# 2026-11-17: with MEM=0.30 and no sequence cap, the engine ran at 100% KV-cache usage with ~150
# requests in flight and crashed ("CUDA error: an illegal memory access", vLLM 0.11). MAX_NUM_SEQS
# caps concurrent sequences so the cache is not driven to saturation.
# RESTART=1 restarts the server automatically after it exits (runs wait for it; see run_replication.py).
set -euo pipefail

MODEL="${MODEL:-Qwen/Qwen3-4B-Instruct-2507}"
GPU="${GPU:-0}"
MEM="${MEM:-0.40}"
PORT="${PORT:-8011}"
# The improver prompt carries 10 full model responses (max_tokens 4096 each), so it can exceed 32K.
MAX_LEN="${MAX_LEN:-65536}"
MAX_NUM_SEQS="${MAX_NUM_SEQS:-96}"
RESTART="${RESTART:-0}"

export CUDA_VISIBLE_DEVICES="${GPU}"
export HF_HOME="${HF_HOME:-${HOME}/.cache/huggingface}"
export TMPDIR="${TMPDIR:-${HOME}/tmp}"
mkdir -p "${TMPDIR}"

serve() {
  echo "$(date -Is) Serving ${MODEL} on GPU ${GPU}, gpu_memory_utilization=${MEM}," \
       "max_model_len=${MAX_LEN}, max_num_seqs=${MAX_NUM_SEQS}, port ${PORT}"
  vllm serve "${MODEL}" \
    --host 127.0.0.1 --port "${PORT}" \
    --gpu-memory-utilization "${MEM}" \
    --max-model-len "${MAX_LEN}" \
    --max-num-seqs "${MAX_NUM_SEQS}" \
    --dtype bfloat16 \
    --seed 0
}

if [ "${RESTART}" = "1" ]; then
  while true; do
    serve || true
    echo "$(date -Is) vLLM server exited; restarting in 15 s"
    sleep 15
  done
else
  serve
fi
