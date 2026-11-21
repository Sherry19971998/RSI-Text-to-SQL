import random

import pytest

from rsi.frontier import question_stats, select


def fake(n_q=200, n_s=8, seed=0):
    rng = random.Random(seed)
    out = []
    for q in range(n_q):
        p = rng.random() ** 2  # many hard questions
        for k in range(n_s):
            out.append({"traj_id": f"q{q}#{k}", "qid": f"q{q}", "db_id": f"db{q % 10}",
                        "correct": rng.random() < p, "safe_all": True, "n_turns": 1,
                        "n_failed_exec": 0, "n_empty": 0, "recovered": False,
                        "schema_ok_all": True, "n_out_tokens": 100})
    return out


@pytest.mark.parametrize("rule", ["random", "hard", "frontier", "mix"])
def test_rules_return_k_distinct_correct(rule):
    trajs = fake()
    qs = question_stats(trajs)
    ids, summ = select(rule, trajs, qs, set(), K=120, seed=0)
    by = {t["traj_id"]: t for t in trajs}
    assert len(ids) == 120 == len(set(ids)) and all(by[i]["correct"] for i in ids)
    assert select(rule, trajs, qs, set(), K=120, seed=0)[0] == ids  # deterministic


def test_frontier_prefers_rare_and_newly_solved_and_caps_duplicates():
    trajs = fake()
    qs = question_stats(trajs)
    rate = lambda t: qs[t["qid"]][0] / qs[t["qid"]][1]
    by = {t["traj_id"]: t for t in trajs}
    _, s_rand = select("random", trajs, qs, set(), K=120, seed=0)
    ids, s_front = select("frontier", trajs, qs, set(), K=120, seed=0)
    assert s_front["mean_question_pass_rate"] < s_rand["mean_question_pass_rate"]
    per_q = {}
    for i in ids:
        per_q[by[i]["qid"]] = per_q.get(by[i]["qid"], 0) + 1
    assert max(per_q.values()) <= 2
    # questions solved earlier go last: mark every solved question except a few as previously solved
    solved = sorted({t["qid"] for t in trajs if t["correct"]})
    prev = set(solved[5:])
    ids2, s2 = select("frontier", trajs, qs, prev, K=120, seed=0)
    first = {by[i]["qid"] for i in ids2[:5]}
    assert first <= set(solved[:5]) and s2["n_newly_solved_q"] == 5


def test_mix_is_half_frontier():
    trajs = fake()
    qs = question_stats(trajs)
    f, _ = select("frontier", trajs, qs, set(), K=120, seed=0)
    m, _ = select("mix", trajs, qs, set(), K=120, seed=0)
    assert m[:60] == f[:60] and len(set(m)) == 120


def test_ablation_variants_remove_one_component_each():
    trajs = fake(n_q=600, n_s=8)   # many more solvable questions than K, as in the real pool
    qs = question_stats(trajs)
    by = {t["traj_id"]: t for t in trajs}
    solved = sorted({t["qid"] for t in trajs if t["correct"]})
    prev = set(solved[10:])                       # 10 newly solved questions this round
    K = 120
    pick = lambda rule: select(rule, trajs, qs, prev, K=K, seed=0)
    full, s_full = pick("frontier")
    _, s_nonew = pick("frontier_no_newly")
    _, s_norar = pick("frontier_no_rarity")
    nocap, _ = pick("frontier_no_cap")
    dd, s_dd = pick("dedup")
    assert pick("frontier_no_topup")[0] == full    # same selection; only the input data differs
    assert s_full["n_newly_solved_q"] == 10 and s_nonew["n_newly_solved_q"] < 10
    assert s_norar["n_newly_solved_q"] == 10
    assert s_norar["mean_question_pass_rate"] > s_full["mean_question_pass_rate"]
    per_q = lambda ids: max(sum(by[i]["qid"] == q for i in ids) for q in {by[i]["qid"] for i in ids})
    assert per_q(nocap) > 1 and len({by[i]["qid"] for i in nocap}) < len({by[i]["qid"] for i in full})
    assert len(dd) == K and s_dd["n_unique_q"] == K


def test_rare_first_is_rarity_order_without_newly_or_cap():
    trajs = fake(n_q=600, n_s=8)
    qs = question_stats(trajs)
    solved = sorted({t["qid"] for t in trajs if t["correct"]})
    prev = set(solved[10:])
    by = {t["traj_id"]: t for t in trajs}
    ids, summ = select("rare_first", trajs, qs, prev, K=120, seed=0)
    rates = [qs[by[i]["qid"]][0] / qs[by[i]["qid"]][1] for i in ids]
    assert rates == sorted(rates)                      # strictly rarest first
    _, s_rand = select("random", trajs, qs, prev, K=120, seed=0)
    assert summ["mean_question_pass_rate"] < s_rand["mean_question_pass_rate"]


def test_informative_drops_always_solved_questions():
    trajs = fake(n_q=600)
    qs = question_stats(trajs)
    by = {t["traj_id"]: t for t in trajs}
    ids, _ = select("informative", trajs, qs, set(), K=120, seed=0)
    assert len(set(ids)) == 120 and all(by[i]["correct"] for i in ids)
    assert all(qs[by[i]["qid"]][0] < qs[by[i]["qid"]][1] for i in ids)


def test_cartography_prefers_variable_questions_plus_some_easy():
    trajs = fake(n_q=600)
    qs = question_stats(trajs)
    by = {t["traj_id"]: t for t in trajs}
    rate = {q: c / n for q, (c, n) in qs.items()}
    ids, _ = select("cartography", trajs, qs, set(), K=120, seed=0)
    assert len(set(ids)) == 120 and all(by[i]["correct"] for i in ids)
    amb = [rate[by[i]["qid"]] for i in ids[:108]]
    assert all(0.2 <= p <= 0.8 for p in amb)      # round 1: binomial std is highest near p = 0.5
    assert sum(rate[by[i]["qid"]] == 1.0 for i in ids[108:]) == 12   # easy tail
    # with history, a question whose pass rate jumped is the most variable one
    q_jump = next(q for q, p in rate.items() if p == 1.0)
    hist = {q: [p] for q, p in rate.items()}
    hist[q_jump] = [0.0]
    ids2, _ = select("cartography", trajs, qs, set(), K=120, seed=0, history=hist)
    assert by[ids2[0]]["qid"] == q_jump
