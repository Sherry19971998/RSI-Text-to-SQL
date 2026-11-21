#!/usr/bin/env bash
# Space-saving BIRD setup for Phase 0/1: train.json + the smallest train databases only.
# Idempotent: reuses an already-extracted train_databases.zip, otherwise downloads train.zip.
# BIRD dev (the final test set) is not needed until final reporting and is removed here.
set -euo pipefail
cd "$(dirname "$0")/.."
B=data/bird
mkdir -p "$B"

find_one() { find "$B" -name "$1" -not -path '*__MACOSX*' | head -1; }
zip_ok() { [ -n "$1" ] && python -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1])" "$1" 2>/dev/null; }

INNER=$(find_one train_databases.zip)
if ! zip_ok "$INNER"; then
  [ -f "$B/train.zip" ] || wget -c -P "$B" https://bird-bench.oss-cn-beijing.aliyuncs.com/train.zip
  unzip -o "$B/train.zip" '*train.json' '*train_databases.zip' -x '__MACOSX/*' -d "$B"
  INNER=$(find_one train_databases.zip)
  zip_ok "$INNER" || { echo "train_databases.zip is damaged; delete $B and rerun"; exit 1; }
fi
TRAIN_JSON=$(find_one train.json)
echo "train.json:          $TRAIN_JSON"
echo "train_databases.zip: $INNER ($(du -h "$INNER" | cut -f1))"

# Free space: the outer zip, the partial (quota-truncated) full extraction, and dev.
rm -f "$B/train.zip"
rm -rf "$(dirname "$INNER")/train_databases"
rm -rf "$B/dev.zip" "$B"/dev "$B"/dev_*

python scripts/extract_bird_subset.py --train-json "$TRAIN_JSON" --db-zip "$INNER" \
    --out "$B/train/dbs" "$@"
du -sh "$B"/* 2>/dev/null
