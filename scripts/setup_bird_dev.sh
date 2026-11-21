#!/usr/bin/env bash
# Download BIRD dev (the final test set) and build data/splits/test.jsonl.
# Check https://bird-bench.github.io/ if the URL moved.
set -euo pipefail
cd "$(dirname "$0")/.."
D=data/bird_dev
mkdir -p "$D"
find_one() { find "$D" -name "$1" -not -path '*__MACOSX*' | head -1; }

if [ -z "$(find_one dev.json)" ] || [ -z "$(find "$D" -name '*.sqlite' -not -path '*__MACOSX*' | head -1)" ]; then
  [ -f "$D/dev.zip" ] || wget -c -P "$D" https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip
  unzip -qo "$D/dev.zip" -x '__MACOSX/*' -d "$D"
  INNER=$(find_one dev_databases.zip)
  [ -n "$INNER" ] && unzip -qo "$INNER" -x '__MACOSX/*' -d "$(dirname "$INNER")" && rm -f "$INNER"
  rm -f "$D/dev.zip"
fi
DEV_JSON=$(find_one dev.json)
DB_ROOT=$(dirname "$(find "$D" -name '*.sqlite' -not -path '*__MACOSX*' | head -1)")/..
echo "dev.json: $DEV_JSON"; echo "databases: $DB_ROOT"
python scripts/prepare_test.py --dev-json "$DEV_JSON" --dev-db-root "$DB_ROOT"
du -sh "$D"
