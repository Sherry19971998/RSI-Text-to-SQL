#!/usr/bin/env bash
# Download BIRD train + dev into data/bird. Check https://bird-bench.github.io/ if a URL moved.
set -euo pipefail
mkdir -p data/bird && cd data/bird

[ -f train.zip ] || wget -c https://bird-bench.oss-cn-beijing.aliyuncs.com/train.zip
[ -f dev.zip ]   || wget -c https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip

unzip -qn train.zip
unzip -qn dev.zip
# The archives nest the databases in a second zip; layouts differ between releases.
for z in $(find . -name 'train_databases.zip' -o -name 'dev_databases.zip'); do
  unzip -qn "$z" -d "$(dirname "$z")"
done
find . -maxdepth 3 -name '*.json' | sort
