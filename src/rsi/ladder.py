"""Feedback ladder for diagnosing where execution-feedback self-correction fails.

All levels start from the same initial SQL per question and differ only in the feedback
message the model sees before each revision round:

  r1             execution error / empty result only (failure-gated; Lin et al. 2026 R1)
  intrinsic      "review your query", no execution (Huang et al. 2024)
  exec           execution result preview (or error) for every query (Self-Debug style)
  oracle_bit     exec + "this result is incorrect"; correct queries get no feedback
  oracle_clause  oracle_bit + which clause to change (Tyen et al. 2024; rsi.localize)
  oracle_shape   oracle_clause + row / column count of the correct result

Levels r1 / intrinsic / exec are deployable; the oracle_* levels use gold and exist only
to separate detection (is it wrong?), localization (where?) and repair (how?).
The loop is model-agnostic: `generate(list_of_messages) -> list[(text, out_tokens, in_tokens)]`.
"""
from __future__ import annotations

import re

import sqlglot

from .localize import hint_slots, localize_many
from .prompts import extract_sql
from .sandbox import check_sql, execute_many

LEVELS = ("r1", "intrinsic", "exec", "oracle_bit", "oracle_clause", "oracle_shape")
ORACLE = {"oracle_bit", "oracle_clause", "oracle_shape"}

_ANSWER = "Give the final query in a ```sql block."
_KEEP = ("If the query already answers the question correctly, repeat it unchanged; "
         "otherwise revise it. " + _ANSWER)


def _preview(r: dict, n_preview: int = 5) -> str:
    if not r["ok"]:
        return f"Execution failed:\n{r['error']}"
    if r["n_rows"] == 0:
        return "The query executed and returned 0 rows."
    rows = "\n".join(" | ".join(map(str, row)) for row in r["preview"][:n_preview])
    more = f"\n... ({r['n_rows']} rows in total)" if r["n_rows"] > n_preview else ""
    trunc = " (truncated)" if r.get("truncated") else ""
    return f"The query executed and returned {r['n_rows']} row(s){trunc}:\n{rows}{more}"


def _slots_text(slots) -> str:
    return " and ".join(slots) if len(slots) <= 2 else ", ".join(slots[:-1]) + " and " + slots[-1]


def feedback(level: str, r: dict, *, correct: bool, loc: dict | None, item: dict) -> str | None:
    """Message for the next round, or None when this level gives no feedback (the query
    is kept as final)."""
    if level == "r1":
        if r["ok"] and r["n_rows"] > 0:
            return None
        return _preview(r) + "\nFix the query. " + _ANSWER
    if level == "intrinsic":
        return ("Review your SQL query carefully against the question, the evidence and the "
                "schema, and look for mistakes. " + _KEEP)
    if level == "exec":
        return _preview(r) + "\n" + _KEEP
    # oracle levels: the oracle stops at correct queries
    if correct:
        return None
    msg = _preview(r) + "\nThis result is incorrect."
    if level in ("oracle_clause", "oracle_shape") and loc is not None:
        slots, basis = hint_slots(loc)
        if slots and basis == "single" and len(slots) > 1:
            msg += f" Changing any one of these clauses could fix it: {_slots_text(slots)}."
        elif slots and basis in ("single", "pair"):
            msg += f" The error is in the {_slots_text(slots)} clause{'s' if len(slots) > 1 else ''}."
        elif slots:
            msg += f" The {_slots_text(slots)} clause{'s' if len(slots) > 1 else ''} may need to change."
    if level == "oracle_shape":
        msg += (f" The correct result has {item['gold_n_rows']} row(s) and "
                f"{item['gold_n_cols']} column(s).")
    return msg + " Revise the query. " + _ANSWER


def _norm(sql):
    if not sql:
        return None
    try:
        return sqlglot.parse_one(sql, read="sqlite").sql(dialect="sqlite", normalize=True)
    except Exception:
        return re.sub(r"\s+", " ", sql.strip().lower())


def _execute(states, items, cfg):
    sqls = [s["sql"] for s in states]
    checks = [check_sql(q) for q in sqls]
    res = execute_many([(it["db_path"], q if c.safe else None)
                        for it, q, c in zip(items, sqls, checks)],
                       timeout=cfg["exec_timeout"], workers=cfg["workers"],
                       n_preview=cfg.get("n_preview", 5))
    out = []
    for it, q, c, r in zip(items, sqls, checks, res):
        if not c.safe:
            r = {**r, "error": f"blocked: {c.reason}" if q else "no SQL found in response"}
        r["correct"] = bool(r["ok"] and not r["truncated"] and r["hash"] == it["gold_hash"])
        out.append(r)
    return out


def run_level(generate, items, initial, level, *, rounds=3, exec_timeout=10.0, workers=8,
              n_preview=5):
    """items: test items (need db_path, gold_sql, gold_hash, gold_n_rows, gold_n_cols).
    initial: per item {"messages": [...system, user, assistant], "sql": str}.
    Returns one record per item with the SQL and correctness after every round."""
    assert level in LEVELS, level
    cfg = {"exec_timeout": exec_timeout, "workers": workers, "n_preview": n_preview}
    states = [{"messages": list(x["messages"]), "sql": x["sql"]} for x in initial]
    res = _execute(states, items, cfg)
    recs = [{"qid": it["qid"], "level": level,
             "history": [{"round": 0, "sql": s["sql"], "correct": r["correct"], "ok": r["ok"],
                          "n_rows": r["n_rows"], "changed": False}],
             "out_tokens": 0, "in_tokens": 0, "calls": 0, "stop": None}
            for it, s, r in zip(items, states, res)]
    active = list(range(len(items)))
    last = dict(enumerate(res))
    for rnd in range(1, rounds + 1):
        if not active:
            break
        locs = {}
        if level in ("oracle_clause", "oracle_shape"):
            need = [i for i in active if not last[i]["correct"]]
            got = localize_many([{"db_path": items[i]["db_path"], "pred_sql": states[i]["sql"],
                                  "gold_sql": items[i]["gold_sql"], "gold_hash": items[i]["gold_hash"]}
                                 for i in need], timeout=exec_timeout, workers=workers)
            locs = dict(zip(need, got))
        prompts, ids = [], []
        for i in active:
            msg = feedback(level, last[i], correct=last[i]["correct"], loc=locs.get(i), item=items[i])
            if msg is None:
                recs[i]["stop"] = "no_feedback"
                continue
            if i in locs:
                recs[i]["history"][-1]["loc"] = locs[i]
            states[i]["messages"].append({"role": "user", "content": msg})
            prompts.append(states[i]["messages"])
            ids.append(i)
        if not ids:
            break
        gens = generate(prompts)
        new_states = []
        for i, (text, n_out, n_in) in zip(ids, gens):
            states[i]["messages"].append({"role": "assistant", "content": text})
            prev = states[i]["sql"]
            states[i]["sql"] = extract_sql(text) or prev
            recs[i]["out_tokens"] += n_out
            recs[i]["in_tokens"] += n_in
            recs[i]["calls"] += 1
            new_states.append(i)
        new_res = _execute([states[i] for i in new_states], [items[i] for i in new_states], cfg)
        still = []
        for i, r in zip(new_states, new_res):
            changed = _norm(states[i]["sql"]) != _norm(recs[i]["history"][-1]["sql"])
            recs[i]["history"].append({"round": rnd, "sql": states[i]["sql"], "correct": r["correct"],
                                       "ok": r["ok"], "n_rows": r["n_rows"], "changed": changed})
            last[i] = r
            if not changed and level not in ORACLE and level != "r1":
                recs[i]["stop"] = "unchanged"  # model kept its query: converged
            else:
                still.append(i)
        active = still
    for rec in recs:
        rec["stop"] = rec["stop"] or "budget"
    return recs


def summarize(recs, rounds):
    """Per round t: accuracy, wrong->correct and correct->wrong rates relative to round 0."""
    n = len(recs)
    init = [r["history"][0]["correct"] for r in recs]
    n_c, n_w = sum(init), n - sum(init)
    out = {"n": n, "init_acc": n_c / n if n else 0.0, "rounds": []}
    # Wrong initial SQL that executes and returns rows: failure-gated repair (r1) never sees it.
    silent = sum(1 for r, i in zip(recs, init) if not i and r["history"][0]["ok"] and r["history"][0]["n_rows"] > 0)
    out["init_wrong_silent_share"] = silent / n_w if n_w else 0.0
    for t in range(rounds + 1):
        at = [r["history"][min(t, len(r["history"]) - 1)] for r in recs]
        fin = [h["correct"] for h in at]
        w2c = sum(f and not i for f, i in zip(fin, init))
        c2w = sum(i and not f for f, i in zip(fin, init))
        edit_c = sum(any(h["changed"] for h in r["history"][1:t + 1]) for r, i in zip(recs, init) if i)
        edit_w = sum(any(h["changed"] for h in r["history"][1:t + 1]) for r, i in zip(recs, init) if not i)
        # upper bound for rolling back: correct at some round <= t (an oracle picks the round)
        best = sum(any(h["correct"] for h in r["history"][:t + 1]) for r in recs)
        out["rounds"].append({
            "round": t, "acc": sum(fin) / n if n else 0.0,
            "acc_rollback_oracle": best / n if n else 0.0,
            "w2c": w2c, "c2w": c2w, "w2c_rate": w2c / n_w if n_w else 0.0,
            "c2w_rate": c2w / n_c if n_c else 0.0, "net": (w2c - c2w) / n if n else 0.0,
            "edit_rate_correct": edit_c / n_c if n_c else 0.0,
            "edit_rate_wrong": edit_w / n_w if n_w else 0.0,
        })
    out["out_tokens"] = sum(r["out_tokens"] for r in recs)
    out["in_tokens"] = sum(r["in_tokens"] for r in recs)
    out["calls"] = sum(r["calls"] for r in recs)
    return out
