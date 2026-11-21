"""Compare two BIRD dev question files question by question (guide E.3: one dev version for both experiments).

Typical use: LSE's bundled dev.json against the dev_20240627 dev.json used by RoboPhD.

    python scripts/check_dev_version.py --a A/dev.json --b B/dev.json [--out diff.json]

Matches questions by question_id and compares db_id, question, evidence and the gold SQL
(whitespace-normalized). Exit code is 0 when identical, 1 when any difference is found.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

FIELDS = ["db_id", "question", "evidence", "SQL"]


def norm(s: Any) -> str:
    return " ".join(str(s or "").split())


def load(path: Path) -> Dict[Any, Dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):  # some dumps wrap the list
        data = data.get("data") or data.get("questions") or list(data.values())
    out = {}
    for item in data:
        qid = item.get("question_id")
        if qid is None:
            raise ValueError(f"{path}: item without question_id")
        out[qid] = item
    return out


def compare(a: Dict[Any, Dict], b: Dict[Any, Dict]) -> Dict[str, Any]:
    only_a = sorted(set(a) - set(b))
    only_b = sorted(set(b) - set(a))
    diffs: List[Dict[str, Any]] = []
    counts = {f: 0 for f in FIELDS}
    for qid in sorted(set(a) & set(b)):
        changed = [f for f in FIELDS if norm(a[qid].get(f)) != norm(b[qid].get(f))]
        for f in changed:
            counts[f] += 1
        if changed:
            diffs.append({"question_id": qid, "fields": changed,
                          **{f"a_{f}": a[qid].get(f) for f in changed},
                          **{f"b_{f}": b[qid].get(f) for f in changed}})
    return {"n_a": len(a), "n_b": len(b), "n_common": len(set(a) & set(b)),
            "only_in_a": only_a, "only_in_b": only_b, "field_diff_counts": counts,
            "n_questions_differing": len(diffs), "diffs": diffs}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--a", required=True)
    p.add_argument("--b", required=True)
    p.add_argument("--out")
    args = p.parse_args()
    rep = compare(load(Path(args.a)), load(Path(args.b)))
    print(f"A: {rep['n_a']} questions, B: {rep['n_b']}, common: {rep['n_common']}")
    print(f"only in A: {len(rep['only_in_a'])}, only in B: {len(rep['only_in_b'])}")
    print(f"questions differing: {rep['n_questions_differing']}  by field: {rep['field_diff_counts']}")
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"details -> {args.out}")
    identical = not rep["only_in_a"] and not rep["only_in_b"] and rep["n_questions_differing"] == 0
    print("IDENTICAL" if identical else "DIFFERENT")
    return 0 if identical else 1


if __name__ == "__main__":
    sys.exit(main())
