#!/usr/bin/env bash
# Set up the LSE experiment on a Linux machine:
#   1. clone the upstream repo into third_party/ at the pinned commit,
#   2. install the upstream environment (uv venv + requirements: vllm 0.11, torch 2.8),
#   3. download the BIRD databases with the upstream helper.
#
# Environment variables:
#   SKIP_INSTALL=1   skip step 2 (e.g. environment already built)
#   SKIP_DATA=1      skip step 3
#   WITH_TRAIN=1     also download the BIRD train databases (needed for the pilot, E.8 step 3)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UPSTREAM_URL="https://github.com/chenyn66/learning-to-self-evolve.git"
UPSTREAM_COMMIT="9eb5eac"
UP="${HERE}/third_party/learning-to-self-evolve"

# 1. upstream at the pinned commit
if [ ! -d "${UP}/.git" ]; then
  mkdir -p "${HERE}/third_party"
  git clone "${UPSTREAM_URL}" "${UP}"
fi
git -C "${UP}" fetch -q origin
git -C "${UP}" checkout -q "${UPSTREAM_COMMIT}"
actual="$(git -C "${UP}" rev-parse --short=7 HEAD)"
if [ "${actual}" != "${UPSTREAM_COMMIT}" ]; then
  echo "Upstream is at ${actual}, expected ${UPSTREAM_COMMIT}" >&2
  exit 1
fi
if [ -n "$(git -C "${UP}" status --porcelain)" ]; then
  echo "Warning: upstream checkout has local modifications; our code must not edit third_party/." >&2
fi
echo "Upstream ready at ${UP} (${actual})"

# 2. environment (Linux; upstream imports vLLM and torch at module load)
if [ "${SKIP_INSTALL:-0}" != "1" ]; then
  if [ "$(uname -s)" != "Linux" ]; then
    echo "Upstream needs Linux (vLLM). Re-run with SKIP_INSTALL=1 SKIP_DATA=1 on other systems." >&2
    exit 1
  fi
  bash "${UP}/scripts/install.sh"
fi

# 3. BIRD databases (question files are already bundled in upstream data/bird)
if [ "${SKIP_DATA:-0}" != "1" ]; then
  bash "${UP}/scripts/setup_bird_data.sh" dev
  if [ "${WITH_TRAIN:-0}" = "1" ]; then
    bash "${UP}/scripts/setup_bird_data.sh" train
  fi
fi

echo "Done. Next: source ${UP}/.venv/bin/activate && export PYTHONPATH=${HERE}:\${PYTHONPATH:-}"
