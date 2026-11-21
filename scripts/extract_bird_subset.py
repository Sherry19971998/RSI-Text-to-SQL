"""Extract only the smallest BIRD train databases, until they cover enough questions.

Saves disk: BIRD train databases total ~30 GB unpacked, but a handful of huge databases
dominate that. Only the .sqlite files are extracted (description CSVs are not used).

python scripts/extract_bird_subset.py --train-json data/bird/train/train.json \
    --db-zip data/bird/train/train_databases.zip --out data/bird/train/dbs --dry-run
"""
import argparse
import json
import shutil
import zipfile
from collections import Counter
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-json", required=True)
    ap.add_argument("--db-zip", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-questions", type=int, default=5000,
                    help="pool (3000) + util_val (1000) + margin for dropped gold SQL / db granularity")
    ap.add_argument("--max-db-mb", type=float, default=1500, help="never take a database larger than this")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    n_q = Counter(x["db_id"] for x in json.loads(Path(args.train_json).read_text()))
    zf = zipfile.ZipFile(args.db_zip)
    members = {}
    for info in zf.infolist():
        p = Path(info.filename)
        if p.suffix == ".sqlite" and "__MACOSX" not in p.parts and p.stem == p.parent.name:
            members[p.parent.name] = info

    cands = sorted((db for db in members if n_q[db] > 0), key=lambda db: members[db].file_size)
    chosen, total_q, total_b = [], 0, 0
    for db in cands:
        if total_q >= args.min_questions:
            break
        if members[db].file_size / 2**20 > args.max_db_mb:
            continue
        chosen.append(db)
        total_q += n_q[db]
        total_b += members[db].file_size

    all_b = sum(m.file_size for m in members.values())
    print(f"{len(members)} databases in zip, {all_b / 2**30:.1f} GB unpacked, {sum(n_q.values())} questions")
    print(f"selected {len(chosen)} databases: {total_q} questions, {total_b / 2**30:.2f} GB unpacked")
    for db in chosen:
        print(f"  {db:<40} {members[db].file_size / 2**20:8.1f} MB  {n_q[db]:4d} q")
    if total_q < args.min_questions:
        print(f"WARNING: only {total_q} questions < --min-questions {args.min_questions}; "
              "raise --max-db-mb to include larger databases")
    if args.dry_run:
        return

    out = Path(args.out)
    for db in chosen:
        info = members[db]
        dst = out / db / f"{db}.sqlite"
        if dst.exists() and dst.stat().st_size == info.file_size:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_suffix(".sqlite.part")
        with zf.open(info) as src, open(tmp, "wb") as f:
            shutil.copyfileobj(src, f, length=16 * 2**20)
        tmp.rename(dst)
        print(f"extracted {db}")
    print(f"done -> {out}")


if __name__ == "__main__":
    main()
