"""Hard verification + safety guardrails (Stage 2).

Three independent layers, so a bug in one does not open a write path:
  1. sqlglot static check: exactly one read-only query, no DDL/DML/PRAGMA/ATTACH.
  2. SQLite opened read-only (`mode=ro`).
  3. SQLite authorizer that denies every action except SELECT / READ / FUNCTION.
Execution is bounded by a progress-handler deadline and a row cap.
"""
from __future__ import annotations

import hashlib
import sqlite3
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, field
from typing import Optional

import sqlglot
from sqlglot import exp

_FORBIDDEN_NAMES = [
    "Insert", "Update", "Delete", "Drop", "Create", "Alter", "AlterTable", "Command",
    "Merge", "Pragma", "Attach", "Detach", "Transaction", "Commit", "Rollback", "Set",
    "Use", "Copy", "LoadData",
]
FORBIDDEN = tuple(getattr(exp, n) for n in _FORBIDDEN_NAMES if hasattr(exp, n))
QUERY_TYPES = (exp.Query,) if hasattr(exp, "Query") else (
    exp.Select, exp.Union, exp.Intersect, exp.Except, exp.Subquery)

_ALLOWED_ACTIONS = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    getattr(sqlite3, "SQLITE_FUNCTION", 31),
    getattr(sqlite3, "SQLITE_RECURSIVE", 33),
}


def _authorizer(action, *_):
    return sqlite3.SQLITE_OK if action in _ALLOWED_ACTIONS else sqlite3.SQLITE_DENY


@dataclass
class SqlCheck:
    parse_ok: bool
    safe: bool
    reason: str = ""
    unknown_tables: list = field(default_factory=list)
    unknown_columns: list = field(default_factory=list)

    @property
    def schema_ok(self) -> bool:
        return self.parse_ok and not self.unknown_tables and not self.unknown_columns


def check_sql(sql: Optional[str], schema: Optional[dict] = None) -> SqlCheck:
    """Static admissibility check. `schema` maps lower-cased table -> set of lower-cased
    columns; when given, unknown tables/columns are reported (a grounding feature, not a
    hard filter: execution already rejects truly missing names)."""
    if not sql or not sql.strip():
        return SqlCheck(False, False, "empty")
    try:
        stmts = [s for s in sqlglot.parse(sql, read="sqlite") if s is not None]
    except Exception as e:  # sqlglot raises several error types
        return SqlCheck(False, False, f"parse_error: {str(e)[:200]}")
    if len(stmts) != 1:
        return SqlCheck(True, False, "empty" if not stmts else "multiple_statements")
    stmt = stmts[0]
    if not isinstance(stmt, QUERY_TYPES):
        return SqlCheck(True, False, f"not_a_query: {type(stmt).__name__}")
    bad = next(iter(stmt.find_all(*FORBIDDEN)), None)
    if bad is not None:
        return SqlCheck(True, False, f"forbidden: {type(bad).__name__}")

    check = SqlCheck(True, True)
    if schema is not None:
        ctes = {c.alias_or_name.lower() for c in stmt.find_all(exp.CTE)}
        tables = {t.name.lower() for t in stmt.find_all(exp.Table) if t.name} - ctes
        check.unknown_tables = sorted(tables - set(schema))
        all_cols = set().union(*schema.values()) if schema else set()
        aliases = {a.alias.lower() for a in stmt.find_all(exp.Alias) if a.alias}
        cols = {c.name.lower() for c in stmt.find_all(exp.Column) if c.name and c.name != "*"}
        check.unknown_columns = sorted(cols - all_cols - aliases)
    return check


def _normalize(v):
    # Match Python set semantics used by the BIRD evaluator (1 == 1.0).
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def result_hash(rows) -> str:
    """Order-insensitive, duplicate-insensitive hash: equal iff set(rows) are equal."""
    canon = sorted({repr(tuple(_normalize(v) for v in r)) for r in rows})
    return hashlib.sha1("\n".join(canon).encode()).hexdigest()


def execute_sql(db_path: str, sql: str, timeout: float = 10.0, max_rows: int = 100_000) -> dict:
    """Run one query under all guards. Returns {ok, rows, truncated, error, time}."""
    t0 = time.monotonic()
    deadline = t0 + timeout
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except Exception as e:
        return {"ok": False, "rows": [], "truncated": False, "error": f"connect: {e}", "time": 0.0}
    conn.text_factory = lambda b: b.decode(errors="replace")
    conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
    conn.set_authorizer(_authorizer)
    try:
        rows = conn.execute(sql).fetchmany(max_rows + 1)
        truncated = len(rows) > max_rows
        return {"ok": True, "rows": rows[:max_rows], "truncated": truncated, "error": "",
                "time": time.monotonic() - t0}
    except Exception as e:
        msg = str(e)
        if "interrupted" in msg:
            msg = f"timeout after {timeout:.0f}s"
        elif "not authorized" in msg:
            msg = "blocked: statement not authorized (read-only sandbox)"
        return {"ok": False, "rows": [], "truncated": False, "error": msg[:500],
                "time": time.monotonic() - t0}
    finally:
        conn.close()


def _fmt(v, width=60):
    s = repr(v) if not isinstance(v, str) else v
    return s if len(s) <= width else s[:width] + "..."


def execute_summary(job) -> dict:
    """Process-pool worker: execute and return a small picklable summary
    (hash + preview instead of all rows)."""
    db_path, sql, timeout, max_rows, n_preview = job
    if sql is None:
        return {"ok": False, "error": "no executable query", "n_rows": 0, "truncated": False,
                "hash": None, "preview": [], "time": 0.0}
    r = execute_sql(db_path, sql, timeout, max_rows)
    return {
        "ok": r["ok"],
        "error": r["error"],
        "n_rows": len(r["rows"]),
        "truncated": r["truncated"],
        "hash": result_hash(r["rows"]) if r["ok"] else None,
        "preview": [[_fmt(v) for v in row] for row in r["rows"][:n_preview]],
        "time": r["time"],
    }


def execute_many(jobs, timeout=10.0, workers=8, max_rows=100_000, n_preview=5) -> list[dict]:
    """jobs: list of (db_path, sql_or_None). Order of results matches jobs."""
    payload = [(db, sql, timeout, max_rows, n_preview) for db, sql in jobs]
    if workers <= 1:
        return [execute_summary(p) for p in payload]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(execute_summary, payload, chunksize=8))


def check_dict(c: SqlCheck) -> dict:
    d = asdict(c)
    d["schema_ok"] = c.schema_ok
    return d
