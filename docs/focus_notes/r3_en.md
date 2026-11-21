# R³-SQL (arXiv 2604.25325)

**One line:** Ranks groups of candidate SQLs that give the same execution result, and resamples when the pool likely has no correct SQL. Gets 75.03 EX on BIRD-dev (best among disclosed-size methods).

**How it works:**
- Generate 32 candidates (Arctic-Text2SQL-R1-32B, T=0.8), execute them, and group equal results.
- Rank groups by pairwise wins (R³-7B ranker). Break ties with group size × best pointwise rank.
- A 7B agent checks the pool. If it judges the pool has no correct SQL, it samples 1,024 new candidates and keeps the top 32.
- R³-7B is trained with GRPO, with a bonus reward when its verdict holds after swapping the order.

**Key results:**

| BIRD-dev / 5 benchmarks, 32B generator | Number |
|---|---|
| BIRD-dev EX: R³-SQL vs CHASE-SQL | 75.03 vs 73.34 |
| 5-benchmark avg EX vs best baseline | 70.65 vs 68.70 |
| Candidate recall (avg): with / without resampling | 82.72 / 78.80 |
| BIRD-dev EX without resampling | 74.25 |

**Key formula:**
- r_point(g) = |g| · max_{s∈g} RR_s. Groups are sorted by pairwise wins r_list first, then by r_point (large group with a top-ranked member).
- S ← S̃ if f(S)=0, else S. The pool is replaced only when the agent thinks it has no correct SQL.

**Limits:**
- The pointwise ranker is trained on BIRD and adds noise out of domain.
- It is costly: 1.56 s/query on 8×H200, plus up to 1,024 extra samples per question.

**For our project:**
- Resampling raises coverage, which matches our finding that keeping coverage (frontier) matters.
- Grouping correct trajectories by execution result could make rare_first and frontier count truly distinct answers.
- Their gain comes at selection time; ours comes from training (53.06 → 59.34). The two can be stacked.
