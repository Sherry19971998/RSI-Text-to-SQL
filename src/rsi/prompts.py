"""Prompt construction for the agentic loop: question -> SQL -> execute -> observe -> repair.

Schema inspection is provided up front (CREATE statements + sample rows) rather than
as a tool call; that keeps trajectories reproducible and the loop simple for Phase 0/1.
"""
from __future__ import annotations

import re
import sqlite3
from functools import lru_cache

SYSTEM_PROMPT = (
    "You are an expert SQLite data analyst. Given a database schema, a question and "
    "optional evidence, write ONE SQLite SELECT query that answers the question. "
    "Reason briefly, then give the query in a ```sql code block. You will see the "
    "execution result and may revise the query."
)


def _ro_connect(db_path: str):
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


@lru_cache(maxsize=512)
def schema_text(db_path: str, n_rows: int = 3, max_chars: int = 12000) -> str:
    conn = _ro_connect(db_path)
    conn.text_factory = lambda b: b.decode(errors="replace")
    try:
        tables = conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        parts = []
        for name, ddl in tables:
            block = (ddl or f"CREATE TABLE {name} (...)").strip()
            if n_rows:
                try:
                    rows = conn.execute(f'SELECT * FROM "{name}" LIMIT {n_rows}').fetchall()
                    shown = "\n".join(
                        " | ".join(str(v)[:40] for v in r) for r in rows)
                    block += f"\n/* {len(rows)} example rows:\n{shown}\n*/"
                except sqlite3.Error:
                    pass
            parts.append(block)
    finally:
        conn.close()
    text = "\n\n".join(parts)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n/* schema truncated */"
    return text


@lru_cache(maxsize=512)
def schema_columns(db_path: str) -> dict:
    """lower-cased table -> frozenset of lower-cased columns."""
    conn = _ro_connect(db_path)
    try:
        names = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        out = {}
        for n in names:
            cols = conn.execute(f'PRAGMA table_info("{n}")').fetchall()
            out[n.lower()] = frozenset(c[1].lower() for c in cols)
        return out
    finally:
        conn.close()


def initial_messages(item: dict, schema_max_chars: int = 12000) -> list[dict]:
    schema = schema_text(item["db_path"], max_chars=schema_max_chars)
    user = f"Database schema:\n{schema}\n\nQuestion: {item['question']}"
    if item.get("evidence"):
        user += f"\nEvidence: {item['evidence']}"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def feedback_message(result: dict) -> str:
    if not result["ok"]:
        return (f"Execution failed:\n{result['error']}\n"
                "Fix the query and give the corrected version in a ```sql block.")
    # Only reached for successful-but-empty results (non-empty results end the episode).
    return ("The query executed but returned 0 rows. If the question expects results, "
            "revise the query (check values, joins and filters) and give it in a ```sql block.")


_SQL_BLOCK = re.compile(r"```sql\s*(.*?)```", re.S | re.I)
_ANY_BLOCK = re.compile(r"```\s*(.*?)```", re.S)


def extract_sql(text: str):
    """Last ```sql block; else last code block; else from the last SELECT/WITH onward."""
    for pat in (_SQL_BLOCK, _ANY_BLOCK):
        blocks = pat.findall(text)
        if blocks:
            return blocks[-1].strip().rstrip(";").strip() or None
    m = list(re.finditer(r"\b(SELECT|WITH)\b", text, re.I))
    if m:
        return text[m[-1].start():].strip().rstrip(";").strip() or None
    return None
