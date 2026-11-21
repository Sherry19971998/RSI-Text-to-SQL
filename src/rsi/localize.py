"""Oracle clause localization for a wrong SQL query (diagnosis only, uses gold SQL).

A clause slot is "responsible" for an error if replacing the predicted query's slot by the
gold query's slot makes the result match gold. This is a denotation-based definition, so
equivalent rewrites of a clause that does not matter are not flagged.

Procedure for a top-level SELECT:
  1. canonicalize table aliases (drop an alias when its table occurs once), so slots from
     the two queries can be swapped even when they used different aliases;
  2. list slots whose normalized text differs between pred and gold (`diff_slots`);
  3. try each differing slot alone, then each pair, and keep the swaps whose execution
     result equals gold (`fix_slots`, `fix_basis` = single / pair).
If no swap works (or the query is a UNION etc.), `fix_basis` says why and the hint falls
back to `diff_slots` or to nothing.
"""
from __future__ import annotations

from itertools import combinations

import sqlglot
from sqlglot import exp

from .sandbox import execute_many

# slot name -> Select arg keys ("from_" in newer sqlglot, "from" in older)
SLOTS = {
    "SELECT": ("expressions", "distinct"),
    "FROM/JOIN": ("from_", "from", "joins"),
    "WHERE": ("where",),
    "GROUP BY": ("group",),
    "HAVING": ("having",),
    "ORDER BY/LIMIT": ("order", "limit", "offset"),
}


def _parse(sql):
    try:
        stmts = [s for s in sqlglot.parse(sql, read="sqlite") if s is not None]
    except Exception:
        return None
    return stmts[0] if len(stmts) == 1 else None


def canonicalize_aliases(tree: exp.Expression) -> exp.Expression:
    """Drop table aliases when every alias names a distinct table that occurs once in the
    whole query; column qualifiers are rewritten to the table name. Otherwise (self-joins,
    an alias reused across subqueries) the tree is returned unchanged."""
    tree = tree.copy()
    tables = list(tree.find_all(exp.Table))
    names = [t.name.lower() for t in tables]
    aliased = [t for t in tables if t.alias]
    aliases = [t.alias.lower() for t in aliased]
    if not aliased or len(set(names)) != len(names) or len(set(aliases)) != len(aliases):
        return tree
    if any(t.alias.lower() in set(names) - {t.name.lower()} for t in aliased):
        return tree  # an alias shadows another table's name
    to_table = {t.alias.lower(): t.this.copy() for t in aliased}
    for col in tree.find_all(exp.Column):
        q = col.table
        if q and q.lower() in to_table:
            col.set("table", to_table[q.lower()].copy())
    for t in aliased:
        t.set("alias", None)
    return tree


def _slot_text(sel: exp.Select, slot: str) -> str:
    parts = []
    for k in SLOTS[slot]:
        v = sel.args.get(k)
        if isinstance(v, list):
            parts.append(" , ".join(x.sql(dialect="sqlite", normalize=True) for x in v))
        elif isinstance(v, exp.Expression):
            parts.append(v.sql(dialect="sqlite", normalize=True))
        elif v:
            parts.append(str(v))
    return " | ".join(p for p in parts if p)


def _swap(pred: exp.Select, gold: exp.Select, slots) -> str:
    hyb = pred.copy()
    for slot in slots:
        for k in SLOTS[slot]:
            if k not in gold.args and k not in hyb.args:
                continue
            v = gold.args.get(k)
            hyb.set(k, [x.copy() for x in v] if isinstance(v, list) else (v.copy() if isinstance(v, exp.Expression) else v))
    return hyb.sql(dialect="sqlite")


def plan(pred_sql: str, gold_sql: str):
    """Static part: returns (status, diff_slots, candidate swaps as [(slots, sql)])."""
    p, g = _parse(pred_sql or ""), _parse(gold_sql)
    if p is None:
        return "pred_parse_error", [], []
    if g is None:
        return "gold_parse_error", [], []
    if not isinstance(p, exp.Select) or not isinstance(g, exp.Select):
        return "unsupported", [], []
    p, g = canonicalize_aliases(p), canonicalize_aliases(g)
    diff = [s for s in SLOTS if _slot_text(p, s) != _slot_text(g, s)]
    if not diff:
        return "no_clause_diff", [], []
    cands = [((s,), _swap(p, g, (s,))) for s in diff]
    if len(diff) >= 2:
        cands += [(pair, _swap(p, g, pair)) for pair in combinations(diff, 2)]
    return "ok", diff, cands


def localize_many(rows, *, timeout=10.0, workers=8):
    """rows: dicts with db_path, pred_sql, gold_sql, gold_hash.
    Returns one dict per row: status, diff_slots, fix_slots, fix_basis."""
    plans = [plan(r["pred_sql"], r["gold_sql"]) for r in rows]
    jobs, owner = [], []
    for i, (r, (_, _, cands)) in enumerate(zip(rows, plans)):
        for slots, sql in cands:
            jobs.append((r["db_path"], sql))
            owner.append((i, slots))
    results = execute_many(jobs, timeout=timeout, workers=workers) if jobs else []
    fixes = [[] for _ in rows]
    for (i, slots), res in zip(owner, results):
        if res["ok"] and not res["truncated"] and res["hash"] == rows[i]["gold_hash"]:
            fixes[i].append(slots)
    out = []
    for r, (status, diff, _), fx in zip(rows, plans, fixes):
        single = [s[0] for s in fx if len(s) == 1]
        pairs = [list(s) for s in fx if len(s) == 2]
        if single:
            basis, fix = "single", single
        elif pairs:
            basis, fix = "pair", pairs[0]
        elif status == "ok":
            basis, fix = "none", []
        else:
            basis, fix = status, []
        out.append({"status": status, "diff_slots": diff, "fix_slots": fix,
                    "fix_basis": basis, "pair_fixes": pairs})
    return out


def hint_slots(loc: dict) -> tuple[list, str]:
    """Slots to name in an oracle-clause hint, and how exact the hint is."""
    if loc["fix_basis"] in ("single", "pair"):
        return loc["fix_slots"], loc["fix_basis"]
    if loc["diff_slots"]:
        return loc["diff_slots"], "diff_only"
    return [], loc["fix_basis"]
