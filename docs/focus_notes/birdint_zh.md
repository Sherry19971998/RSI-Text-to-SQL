# BIRD-INTERACT（arXiv 2510.05318，ICLR 2026）

**一句话：** 模型要多轮询问模拟用户、探索数据库来写 SQL；GPT-5 在 FULL 上只完成 8.67%（c-Interact）/ 17.00%（a-Interact）。

**如何构建：**
- PostgreSQL 数据库 + 知识库 + 不泄露标准答案的 LLM 用户模拟器。
- FULL 600 题，LITE 300 题（库更简单），人为注入歧义。
- 每题：先做有歧义的主任务，再做依赖新数据库状态的追问；覆盖 CRUD，测试脚本判分。
- c-Interact：固定对话，可调试一次；a-Interact：智能体，9 种工具。
- 每个动作耗预算（ask 2，submit 3，execute 1）。

**主要结果：**

| 设置 | 最佳模型 | 主任务 / 追问 SR (%) | Reward* |
|---|---|---|---|
| FULL c-Interact | Gemini-2.5-Pro | 25.00 / 16.33 | 20.92 |
| FULL a-Interact | GPT-5 | 29.17 / 17.00 | 25.52 |
| LITE c-Interact | O3-Mini | 37.33 / 24.33 | 32.93 |
| LITE a-Interact | Claude-Sonnet-3.7 | 34.00 / 17.67 | 29.10 |

**关键公式：**
- SR = 通过全部测试的子任务比例（成功率）。
- 预算 B = 6 + 2·m_amb + 2·λ_pat（歧义越多、用户越耐心，可用动作越多）。

**局限：**
- 用户是模拟的；只测大型 API 模型，单次运行。
- 只支持 PostgreSQL，API 成本高。

**对我们项目：**
- 可在 LITE 上做附加评测，但要换 PostgreSQL（非 SQLite）、加我们没训练过的提问动作、接 API 模拟器。我们的 execute→repair 最接近 a-Interact。
- 轮数越多越好（ITS）。记忆嫁接：GPT-5 用别的模型的澄清记录后明显提升，说明瓶颈是提问而非写 SQL；我们只训练写 SQL 和修复。
