"""Frontier experiment: selection rules that differ in how they treat the model's solving frontier.

All rules choose K correct, safe trajectories from the same generated pool:
  random    uniform over correct trajectories (standard rejection-sampling self-training)
  hard      Phase 1's best strategy: questions in the lowest pass-rate tercile first
  frontier  newly solved questions first (unsolved in every earlier round of this lineage),
            then rare successes (pass rate <= rare_rate), then by ascending pass rate;
            at most max_per_question trajectories per question (duplication hurt in Phase 1)
  mix       half frontier, half random from the rest

Ablations of frontier (each removes one component):
  frontier_no_newly   no newly-solved tier (ordering by pass rate only)
  frontier_no_rarity  newly-solved tier, then questions in random order (no pass-rate ordering)
  frontier_no_cap     same ordering, but all of a question's trajectories taken consecutively
                      instead of one per question first (allows duplication)
  frontier_no_topup   frontier selection on the first 8 samples only (no 32x top-up); the
                      top-up filtering happens in scripts/frontier.py, selection here is frontier
  dedup               one trajectory per question, questions in random order (diversity only)

Simplified rule (what the ablation showed matters):
  rare_first  rarest questions first (ascending pass rate), duplicates allowed, no newly tier

Literature baselines:
  informative  DAPO's dynamic sampling (Yu et al., 2025) as an SFT selection: uniform over correct
               trajectories of questions with 0 < pass rate < 1 (drops always-solved questions)
  cartography  Dataset Cartography (Swayamdipta et al., 2020) with rounds in place of epochs:
               confidence = mean and variability = std of the question's pass rate over this
               lineage's rounds (round 1, a single point: binomial std sqrt(p(1-p))); 90% of K from
               the most variable ("ambiguous") questions, 10% from the most confident ("easy"),
               the paper's recommended mix; at most max_per_question per question
"""
from __future__ import annotations

import random
from collections import defaultdict

import numpy as np

from .batches import build_batches

RULES = ("random", "hard", "frontier", "mix", "frontier_no_newly", "frontier_no_rarity",
         "frontier_no_cap", "frontier_no_topup", "dedup", "rare_first", "informative", "cartography")
# (use newly-solved tier, order by pass rate, one-per-question round-robin)
VARIANTS = {"frontier": (True, True, True), "mix": (True, True, True),
            "frontier_no_topup": (True, True, True), "frontier_no_newly": (False, True, True),
            "frontier_no_rarity": (True, False, True), "frontier_no_cap": (True, True, False),
            "dedup": (False, False, True), "rare_first": (False, True, False)}


def question_stats(trajs) -> dict:
    """qid -> [n_correct, n_samples]."""
    st = defaultdict(lambda: [0, 0])
    for t in trajs:
        st[t["qid"]][0] += int(t["correct"])
        st[t["qid"]][1] += 1
    return dict(st)


def frontier_order(elig, qstats, prev_solved, rng, max_per_question, newly=True, rarity=True,
                   round_robin=True):
    by_q = defaultdict(list)
    for t in elig:
        by_q[t["qid"]].append(t["traj_id"])
    for v in by_q.values():
        rng.shuffle(v)
    tiebreak = {q: rng.random() for q in by_q}
    rate = {q: qstats[q][0] / qstats[q][1] for q in by_q}
    qs = sorted(by_q, key=lambda q: ((q in prev_solved) if newly else False,  # newly solved first
                                     rate[q] if rarity else 0.0, tiebreak[q]))
    if not round_robin:  # a question's trajectories back to back: duplication allowed
        return [t for q in qs for t in by_q[q]]
    return interleave(by_q, qs, max_per_question)  # one per question before any second copy


def interleave(by_q, qs, max_per_question):
    order = []
    for k in range(max_per_question):
        order += [by_q[q][k] for q in qs if len(by_q[q]) > k]
    return order


def cartography_order(elig, qstats, history, rng, K, max_per_question, easy_frac=0.1):
    """90% most variable questions, then 10% most confident ones (Swayamdipta et al., 2020)."""
    by_q = defaultdict(list)
    for t in elig:
        by_q[t["qid"]].append(t["traj_id"])
    for v in by_q.values():
        rng.shuffle(v)
    conf, var = {}, {}
    for q in by_q:
        rates = list(history.get(q, [])) + [qstats[q][0] / qstats[q][1]]
        conf[q] = float(np.mean(rates))
        p = rates[0]
        var[q] = float(np.std(rates)) if len(rates) > 1 else float(np.sqrt(p * (1 - p)))
    tie = {q: rng.random() for q in by_q}
    n_easy = int(round(K * easy_frac))
    ambiguous = interleave(by_q, sorted(by_q, key=lambda q: (-var[q], tie[q])), max_per_question)
    ids = ambiguous[:K - n_easy]
    taken = set(ids)
    easy = interleave(by_q, sorted(by_q, key=lambda q: (-conf[q], tie[q])), max_per_question)
    return ids + [i for i in easy if i not in taken][:n_easy]


def select(rule, trajs, qstats, prev_solved, K, seed, rare_rate=0.125, max_per_question=2,
           history=None):
    """Return (traj_ids, summary). prev_solved: qids solved in any earlier round of this lineage;
    history: qid -> pass rates in earlier rounds of this lineage (cartography only)."""
    if rule not in RULES:
        raise ValueError(f"unknown rule {rule}")
    rng = random.Random(f"{seed}-{rule}")
    elig = [t for t in trajs if t["correct"] and t["safe_all"]]
    if len(elig) < K:
        raise ValueError(f"only {len(elig)} eligible trajectories < K={K}")
    all_ids = [t["traj_id"] for t in elig]
    if rule == "random":
        ids = rng.sample(all_ids, K)
    elif rule == "hard":
        ids = build_batches(trajs, {"hard": 1}, K, seed=seed)[0]["traj_ids"]
    elif rule in ("informative", "cartography"):
        if rule == "informative":
            pool = [t["traj_id"] for t in elig if qstats[t["qid"]][0] < qstats[t["qid"]][1]]
            ids = rng.sample(pool, min(K, len(pool)))
        else:
            ids = cartography_order(elig, qstats, history or {}, rng, K, max_per_question)
        if len(ids) < K:
            taken = set(ids)
            ids += rng.sample([i for i in all_ids if i not in taken], K - len(ids))
    else:
        # same ordering seed for all frontier variants, so they differ only in the component removed
        newly, rarity, rr = VARIANTS[rule]
        order = frontier_order(elig, qstats, prev_solved, random.Random(f"{seed}-frontier-order"),
                               max_per_question if rule != "dedup" else 1, newly, rarity, rr)
        n_front = K // 2 if rule == "mix" else K
        ids = order[:n_front]
        if len(ids) < K:
            taken = set(ids)
            rest = [i for i in all_ids if i not in taken]
            ids += rng.sample(rest, K - len(ids))
    by_id = {t["traj_id"]: t for t in elig}
    qs = [by_id[i]["qid"] for i in ids]
    rates = [qstats[q][0] / qstats[q][1] for q in qs]
    return ids, {
        "rule": rule, "K": len(ids), "n_unique_q": len(set(qs)),
        "n_newly_solved_q": len({q for q in qs if q not in prev_solved}) if prev_solved else 0,
        "n_rare_q": len({q for q, r in zip(qs, rates) if r <= rare_rate}),
        "mean_question_pass_rate": float(np.mean(rates)),
    }
