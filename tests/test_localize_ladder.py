import sqlite3

import pytest

from rsi.ladder import feedback, run_level, summarize
from rsi.localize import canonicalize_aliases, localize_many
from rsi.sandbox import execute_sql, result_hash

GOLD = ("SELECT T1.name FROM school AS T1 JOIN score AS T2 ON T1.id = T2.sid "
        "WHERE T2.year = 2020 ORDER BY T2.avg_math DESC LIMIT 1")
WHERE_WRONG = ("SELECT s.name FROM school s JOIN score t ON s.id = t.sid "
               "WHERE t.year = 2021 ORDER BY t.avg_math DESC LIMIT 1")
TWO_WRONG = ("SELECT school.name FROM school JOIN score ON school.id = score.sid "
             "WHERE score.year = 2021 ORDER BY score.avg_math ASC LIMIT 1")


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "s.sqlite"
    c = sqlite3.connect(p)
    c.executescript("""
        CREATE TABLE school (id INTEGER, name TEXT, county TEXT);
        CREATE TABLE score (sid INTEGER, avg_math INTEGER, year INTEGER);
        INSERT INTO school VALUES (1,'A','X'),(2,'B','Y'),(3,'C','X');
        INSERT INTO score VALUES (1,500,2020),(2,610,2020),(3,580,2021),(1,520,2021);
    """)
    c.commit()
    c.close()
    return str(p)


def _item(db, qid="q1"):
    return {"qid": qid, "db_path": db, "gold_sql": GOLD, "gold_n_rows": 1, "gold_n_cols": 1,
            "gold_hash": result_hash(execute_sql(db, GOLD)["rows"])}


def test_alias_canonicalization_removes_unique_aliases():
    import sqlglot
    out = canonicalize_aliases(sqlglot.parse_one(GOLD)).sql()
    assert "T1" not in out and "school.name" in out


def test_self_join_aliases_kept():
    import sqlglot
    sql = "SELECT a.name FROM school a JOIN school b ON a.county = b.county"
    assert canonicalize_aliases(sqlglot.parse_one(sql)).sql().count(" AS ") == 2


def test_localize_single_and_pair(db):
    it = _item(db)
    rows = [{**it, "pred_sql": s} for s in (WHERE_WRONG, TWO_WRONG, "SELECT name FROM school UNION SELECT county FROM school")]
    a, b, c = localize_many(rows, workers=1)
    assert a["fix_basis"] == "single" and a["fix_slots"] == ["WHERE"]
    assert b["fix_basis"] == "pair" and set(b["fix_slots"]) == {"WHERE", "ORDER BY/LIMIT"}
    assert c["fix_basis"] == "unsupported"


def test_feedback_oracle_stops_on_correct(db):
    r = {"ok": True, "n_rows": 1, "preview": [["B"]], "error": "", "truncated": False}
    assert feedback("oracle_bit", r, correct=True, loc=None, item={}) is None
    assert feedback("r1", r, correct=False, loc=None, item={}) is None
    msg = feedback("oracle_clause", r, correct=False, item={},
                   loc={"fix_basis": "single", "fix_slots": ["WHERE"], "diff_slots": ["WHERE"]})
    assert "incorrect" in msg and "WHERE clause" in msg


def test_run_level_with_fake_model(db):
    items = [_item(db, "q1"), _item(db, "q2")]
    initial = [{"sql": WHERE_WRONG, "messages": []}, {"sql": GOLD, "messages": []}]

    def fixer(prompts):  # fixes the query only when told which clause is wrong
        out = []
        for p in prompts:
            fb = p[-1]["content"]
            sql = GOLD if "WHERE clause" in fb else WHERE_WRONG  # breaks correct ones otherwise
            out.append((f"```sql\n{sql}\n```", 10, 100))
        return out

    clause = run_level(fixer, items, initial, "oracle_clause", rounds=2, workers=1)
    s = summarize(clause, 2)
    assert s["rounds"][-1]["acc"] == 1.0 and s["rounds"][-1]["c2w"] == 0
    assert clause[1]["calls"] == 0  # oracle never touches the correct query

    exe = run_level(fixer, items, initial, "exec", rounds=2, workers=1)
    s = summarize(exe, 2)
    assert s["rounds"][-1]["c2w"] == 1 and s["rounds"][-1]["acc"] == 0.0
    assert exe[0]["stop"] == "unchanged"
