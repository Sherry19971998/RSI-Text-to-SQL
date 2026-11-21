# DySQL-Bench (Sun et al., arXiv 2510.26495)

First author: Linzhuang Sun (University of Chinese Academy of Sciences). Co-authors from Peking University and Tsinghua University; corresponding authors Wentao Zhang and Bin Cui (PKU).

**One line:** A benchmark of 1,072 multi-turn conversational database tasks where a simulated user's requests evolve over turns; even GPT-4o gets only 58.34% overall and 23.81% on Pass^5.

**How it is built:**
- 13 SQLite databases taken from BIRD and Spider 2. Each record is turned into a JSON tree by following foreign keys. GPT-4.1 writes tasks from these trees: a user instruction plus "golden" SQL actions.
- Full CRUD: UPDATE 49.64%, SELECT 28.93%, DELETE 10.80%, INSERT 10.63%. Short tasks (<3 actions) and Long tasks (≥3 actions).
- Quality control: two LLM checkers (DeepSeek-R1, Qwen3-235B) verify each task, missing parameters are added back into the instruction, the golden SQL must execute, and 10 experts check every task.
- Qwen2.5-72B-Instruct plays the user and reveals information turn by turn. The agent sees the DDL and can talk, run SQL or reason. The dialogue ends at ###STOP### or after 30 turns.
- Grading: a task counts as solved only if the final database state, hashed with timestamp columns removed, matches the state left by the golden actions.

**Key results:**

| Item | Number |
|---|---|
| GPT-4o overall (abstract) | Pass^1 58.34%, Pass^5 23.81% |
| Qwen2.5-72B-Instruct, retail world | Pass^1 90.32 → Pass^5 74.19 |
| Gemini-2.5-Flash, retail | Pass^1 0.98 |
| Hallucinated results (agent invents SQL output) | DeepSeek-V3 44.28%, OmniSQL-32B 26.15%, GPT-4o 0.09% |
| Few-shot, avg over CA/EN/PA (0 → 3-shot) | GPT-4o 62.60 → 64.68; Qwen2.5-72B 63.39 → 65.52 |

**Key formula:**
- Pass^k = E_task[ C(c,k) / C(n,k) ], where c of n runs succeed. It is the chance that k random runs of a task all succeed, so it measures consistency.
- Success = [hash(S₂) = hash(S₃)], where S₂ is the final state from the model's actions and S₃ = execute(A_g | S₁) is the state from the golden actions.

**Limits:**
- The simulated user is one LLM (Qwen2.5-72B), so scores depend on how it behaves. Tasks are LLM-generated around a single record and lean toward UPDATE-style transactions, not analytics.
- The tables report scores per domain only. The overall numbers appear only in the abstract, and the task counts do not add up (561 + 501 = 1,062, not 1,072).

**For our project:**
- It fits only partly as a transfer test. It shares BIRD databases and uses execution feedback, but it is conversational with a simulated user, it is mostly writes (CRUD), and it grades the final DB state instead of BIRD EX.
- To use it we would need: a chat/tool prompt format for our 7–8B models, a 72B user simulator served alongside them (heavy GPU cost; we have no local GPU), several runs per task for Pass^k, and support for INSERT/UPDATE/DELETE. Our training data is SELECT-only.
- Pass^k fits our coverage question well. Sharpened self-trained checkpoints should gain on Pass^k (consistency), while the frontier should keep more coverage. Reporting Pass^1 and Pass^5 for θ0 (53.06 BIRD EX) and the frontier (59.34) would test this.
