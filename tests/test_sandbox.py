import sqlite3

import pytest

from rsi.prompts import extract_sql, schema_columns, schema_text
from rsi.sandbox import check_sql, execute_many, execute_sql, result_hash


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "t.sqlite"
    c = sqlite3.connect(p)
    c.executescript("""
        CREATE TABLE singer (id INTEGER PRIMARY KEY, name TEXT, age INTEGER, country TEXT);
        INSERT INTO singer VALUES (1,'A',30,'US'),(2,'B',25,'FR'),(3,'C',40,'US');
    """)
    c.commit()
    c.close()
    return str(p)


def test_select_runs(db):
    r = execute_sql(db, "SELECT name FROM singer WHERE country='US' ORDER BY age")
    assert r["ok"] and r["rows"] == [("A",), ("C",)]


@pytest.mark.parametrize("sql", [
    "DELETE FROM singer",
    "DROP TABLE singer",
    "UPDATE singer SET age = 0",
    "INSERT INTO singer VALUES (9,'Z',1,'X')",
    "CREATE TABLE x (a INT)",
    "PRAGMA writable_schema = 1",
    "ATTACH DATABASE 'other.db' AS o",
    "SELECT 1; DROP TABLE singer",
])
def test_static_check_blocks_writes(sql):
    assert not check_sql(sql).safe


@pytest.mark.parametrize("sql", [
    "DELETE FROM singer",
    "DROP TABLE singer",
    "CREATE TEMP TABLE x (a INT)",
    "PRAGMA writable_schema = 1",
])
def test_runtime_guard_blocks_writes_even_if_static_check_bypassed(db, sql):
    r = execute_sql(db, sql)
    assert not r["ok"]
    assert execute_sql(db, "SELECT count(*) FROM singer")["rows"] == [(3,)]


def test_allowed_queries_pass_static_check():
    for sql in [
        "SELECT * FROM singer",
        "WITH t AS (SELECT age FROM singer) SELECT max(age) FROM t",
        "SELECT name FROM singer UNION SELECT country FROM singer",
        "SELECT replace(name, 'A', 'b') FROM singer",
    ]:
        assert check_sql(sql).safe, sql


def test_recursive_cte_allowed_and_timeout(db):
    r = execute_sql(db, "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c WHERE x<5) SELECT x FROM c")
    assert r["ok"] and len(r["rows"]) == 5
    r = execute_sql(db, "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c) SELECT count(*) FROM c",
                    timeout=0.5)
    assert not r["ok"] and "timeout" in r["error"]


def test_schema_grounding(db):
    schema = schema_columns(db)
    assert check_sql("SELECT name FROM singer", schema).schema_ok
    c = check_sql("SELECT nme FROM singers", schema)
    assert c.safe and c.unknown_tables == ["singers"] and c.unknown_columns == ["nme"]
    assert check_sql("SELECT count(*) AS n FROM singer ORDER BY n", schema).schema_ok


def test_result_hash_is_set_semantics():
    assert result_hash([(1, "a"), (2, "b")]) == result_hash([(2, "b"), (1, "a"), (1, "a")])
    assert result_hash([(1,)]) == result_hash([(1.0,)])
    assert result_hash([(1,)]) != result_hash([(1.5,)])


def test_execute_many_parallel(db):
    res = execute_many([(db, "SELECT 1"), (db, None), (db, "SELECT nope FROM singer")], workers=2)
    assert res[0]["ok"] and not res[1]["ok"] and not res[2]["ok"]
    assert "no such column" in res[2]["error"]


def test_schema_text_and_extract(db):
    s = schema_text(db)
    assert "CREATE TABLE singer" in s and "example rows" in s
    assert extract_sql("think...\n```sql\nSELECT 1;\n```\nfix:\n```sql\nSELECT 2\n```") == "SELECT 2"
    assert extract_sql("The answer is SELECT a FROM b;") == "SELECT a FROM b"
    assert extract_sql("no query here") is None
