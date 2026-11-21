# BIRD-INTERACT (arXiv 2510.05318, ICLR 2026)

**One line:** Text-to-SQL where the model must ask a simulated user and explore the DB over many turns; GPT-5 solves only 8.67% (c-Interact) / 17.00% (a-Interact) of FULL tasks.

**How it is built:**
- PostgreSQL DB + knowledge base + LLM user simulator that refuses to leak the gold SQL.
- FULL 600 tasks, LITE 300 (simpler DBs), with injected ambiguities.
- Each task: an ambiguous main sub-task, then a follow-up that may use the changed DB state; full CRUD, checked by test scripts.
- c-Interact: fixed chat, one debug try. a-Interact: agent with 9 tools.
- Every action costs budget (ask 2, submit 3, execute 1).

**Key results:**

| Setting | Best model | SR main / follow-up (%) | Reward* |
|---|---|---|---|
| FULL c-Interact | Gemini-2.5-Pro | 25.00 / 16.33 | 20.92 |
| FULL a-Interact | GPT-5 | 29.17 / 17.00 | 25.52 |
| LITE c-Interact | O3-Mini | 37.33 / 24.33 | 32.93 |
| LITE a-Interact | Claude-Sonnet-3.7 | 34.00 / 17.67 | 29.10 |

**Key formula:**
- SR = share of sub-tasks passing all tests (plain success).
- Budget B = 6 + 2·m_amb + 2·λ_pat (more ambiguities or patience, more actions).

**Limits:**
- Simulated user; only large API models tested, single run.
- PostgreSQL only; costly API calls.

**For our project:**
- Possible extra test on LITE, but needs PostgreSQL (not SQLite), an "ask" action we never trained, and an API user simulator. Our execute→repair is closest to a-Interact.
- More turns help (ITS). Memory grafting: GPT-5 improves with other models' clarification histories, so asking, not SQL skill, is the bottleneck; our training targets SQL and repair only.
