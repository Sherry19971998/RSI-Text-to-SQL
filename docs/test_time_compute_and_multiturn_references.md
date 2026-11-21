# Test-time compute and multi-turn Text-to-SQL: verified references
# 测试时计算与多轮 Text-to-SQL：已核实的参考文献

Every paper below was checked against the arXiv API on 2026-10-20: arXiv id, title, first author and submission date. A venue is given only when the arXiv record itself states it (comment or journal field). Otherwise the entry says "arXiv". Key numbers come from each paper's abstract, or, for Alpha-SQL, from its full text.

以下每篇论文都在 2026-10-20 通过 arXiv API 核对过：arXiv 编号、标题、第一作者、提交日期。会议/期刊只在 arXiv 记录本身写明时才标注（comment 或 journal 字段），否则只写"arXiv"。关键数字来自各论文摘要（Alpha-SQL 来自全文）。

---

## 1. General test-time compute 通用测试时计算

### 1.1 Foundations and scaling laws 基础与规律

| Paper | First author, year | Venue | Link | What it shows | 中文要点 |
|---|---|---|---|---|---|
| Training Verifiers to Solve Math Word Problems | Cobbe, 2021 | arXiv | [2110.14168](https://arxiv.org/abs/2110.14168) | Introduces GSM8K. A trained verifier that ranks many sampled solutions beats fine-tuning alone. | 提出 GSM8K；用训练好的验证器给多个采样解排序，比单纯微调好。最早的"采样+验证器"工作之一。 |
| Large Language Monkeys: Scaling Inference Compute with Repeated Sampling | Brown, 2024 | arXiv | [2407.21787](https://arxiv.org/abs/2407.21787) | Coverage (share of problems solved by any sample) grows with the number of samples over four orders of magnitude, often log-linearly. On SWE-bench Lite: 15.9% with 1 sample, 56% with 250. Majority voting and reward models plateau after several hundred samples. | 覆盖率随采样数增长跨越四个数量级，常呈对数线性；有自动验证（代码、证明）时覆盖率直接变成准确率；没有验证器时，投票和奖励模型在几百个样本后就不再提升。 |
| Scaling LLM Test-Time Compute Optimally can be More Effective than Scaling Model Parameters | Snell, 2024 | arXiv | [2408.03314](https://arxiv.org/abs/2408.03314) | Studies two mechanisms: searching against process reward models, and revising the answer distribution. Which works best depends on question difficulty, so a per-question "compute-optimal" allocation is more efficient than best-of-N. | 研究两种机制：用过程奖励模型引导搜索、在测试时修正答案分布。哪种好取决于题目难度，所以按题分配计算比统一 best-of-N 更高效。 |
| Inference Scaling Laws: An Empirical Analysis of Compute-Optimal Inference for Problem-Solving with Language Models | Wu, 2024 | arXiv | [2408.00724](https://arxiv.org/abs/2408.00724) | Compares greedy, majority voting, best-of-n, weighted voting and tree search across model sizes. Smaller models plus stronger inference can be Pareto-optimal; Llemma-7B with their tree search beats Llemma-34B on MATH. | 比较贪心、投票、best-of-n、加权投票和树搜索在不同模型大小下的性价比：小模型加强推理可以达到帕累托最优，Llemma-7B 加树搜索胜过 Llemma-34B。 |
| A Survey on Test-Time Scaling in Large Language Models: What, How, Where, and How Well? | Q. Zhang, 2025 | arXiv | [2503.24235](https://arxiv.org/abs/2503.24235) | Survey organised by what to scale, how, where and how well. | 测试时扩展综述，按"扩展什么、怎么扩展、用在哪、效果如何"组织，可作分类依据。 |

### 1.2 Parallel sampling and selection 并行采样与挑选

| Paper | First author, year | Venue | Link | What it shows | 中文要点 |
|---|---|---|---|---|---|
| Self-Consistency Improves Chain of Thought Reasoning in Language Models | X. Wang, 2022 | ICLR 2023 | [2203.11171](https://arxiv.org/abs/2203.11171) | Sample several reasoning paths and take the majority answer. | 采样多条推理链，取多数答案。Text-to-SQL 里"按执行结果投票"的源头。 |
| Let's Verify Step by Step | Lightman, 2023 | arXiv | [2305.20050](https://arxiv.org/abs/2305.20050) | Process supervision (scoring each step) trains a better verifier than outcome supervision for best-of-N on MATH. Releases PRM800K. | 过程监督（每一步打分）训练出的验证器比只看结果的更好；发布 PRM800K。 |
| Solving math word problems with process- and outcome-based feedback | Uesato, 2022 | arXiv | [2211.14275](https://arxiv.org/abs/2211.14275) | Earlier comparison of process- and outcome-based reward models. | 更早对比过程奖励与结果奖励的工作。 |
| CodeT: Code Generation with Generated Tests | B. Chen, 2022 | arXiv | [2207.10397](https://arxiv.org/abs/2207.10397) | Generates test cases with the model and picks code by agreement with the tests. | 让模型自己生成测试用例，按通过情况挑代码；执行信号用于挑选。 |
| LEVER: Learning to Verify Language-to-Code Generation with Execution | Ni, 2023 | ICML 2023 | [2302.08468](https://arxiv.org/abs/2302.08468) | Trains a verifier that uses the program, its execution result and the question; evaluated on Spider and other code tasks. | 训练一个看"程序 + 执行结果 + 问题"的验证器来重排候选，包含 Spider。 |

### 1.3 Sequential refinement 顺序修正

| Paper | First author, year | Venue | Link | What it shows | 中文要点 |
|---|---|---|---|---|---|
| Self-Refine: Iterative Refinement with Self-Feedback | Madaan, 2023 | arXiv | [2303.17651](https://arxiv.org/abs/2303.17651) | The same model writes, critiques and revises its output. | 同一个模型写答案、自我批评、再修改。 |
| Reflexion: Language Agents with Verbal Reinforcement Learning | Shinn, 2023 | arXiv | [2303.11366](https://arxiv.org/abs/2303.11366) | Agents store verbal reflections on failures in memory and retry. | 智能体把失败原因写成文字记忆，下次重试时参考。 |
| Teaching Large Language Models to Self-Debug | X. Chen, 2023 | arXiv | [2304.05128](https://arxiv.org/abs/2304.05128) | The model explains and fixes its code using execution results; includes Spider text-to-SQL. | 模型根据执行结果解释并修改代码，实验包含 Spider Text-to-SQL。 |
| Large Language Models Cannot Self-Correct Reasoning Yet | J. Huang, 2023 | ICLR 2024 | [2310.01798](https://arxiv.org/abs/2310.01798) | Without external feedback, self-correction does not help reasoning and can hurt. | 没有外部反馈时，自我修正对推理无益甚至有害。说明 SQL 执行反馈的价值。 |
| Training Language Models to Self-Correct via Reinforcement Learning (SCoRe) | Kumar, 2024 | arXiv | [2409.12917](https://arxiv.org/abs/2409.12917) | Multi-turn RL that trains the model to correct its own answer. | 用多轮强化学习专门训练模型的自我修正能力。 |

### 1.4 Tree search 树搜索

| Paper | First author, year | Venue | Link | What it shows | 中文要点 |
|---|---|---|---|---|---|
| Thinking Fast and Slow with Deep Learning and Tree Search (ExIt) | Anthony, 2017 | arXiv | [1705.08439](https://arxiv.org/abs/1705.08439) | Expert Iteration: tree search produces better moves, and a network is trained to imitate them. | 专家迭代：树搜索找更好的走法，再训练网络模仿它。"搜索后摊销"的经典来源。 |
| Tree of Thoughts: Deliberate Problem Solving with Large Language Models | Yao, 2023 | NeurIPS 2023 | [2305.10601](https://arxiv.org/abs/2305.10601) | Explores a tree of intermediate thoughts with lookahead and backtracking. | 在中间推理步骤上建树，可前瞻和回退。 |
| Reasoning with Language Model is Planning with World Model (RAP) | Hao, 2023 | EMNLP 2023 | [2305.14992](https://arxiv.org/abs/2305.14992) | Uses MCTS over reasoning steps with the LLM as world model. | 把 LLM 当世界模型，用 MCTS 规划推理步骤。 |
| Mutual Reasoning Makes Smaller LLMs Stronger Problem-Solvers (rStar) | Qi, 2024 | arXiv | [2408.06195](https://arxiv.org/abs/2408.06195) | MCTS with a rich set of human-like reasoning actions plus mutual verification by a second small model. Alpha-SQL borrows its question-rephrasing action. | 用 MCTS 搜索类人推理动作，再由另一个小模型互相验证；Alpha-SQL 的问题改写动作来自这里。 |
| ReST-MCTS*: LLM Self-Training via Process Reward Guided Tree Search | D. Zhang, 2024 | NeurIPS 2024 | [2406.03816](https://arxiv.org/abs/2406.03816) | Tree search guided by a process reward produces traces that are used to self-train both the policy and the reward model. | 用过程奖励引导树搜索，再用搜到的轨迹自训练策略模型和奖励模型。 |
| rStar-Math: Small LLMs Can Master Math Reasoning with Self-Evolved Deep Thinking | Guan, 2025 | arXiv | [2501.04519](https://arxiv.org/abs/2501.04519) | Several rounds of MCTS-generated data plus a process preference model let small models self-evolve. | 多轮"MCTS 生成数据→训练"的自我进化，小模型达到很强的数学推理。与我们的多轮自训练最像。 |

### 1.5 Long reasoning models and agents 长推理模型与智能体

| Paper | First author, year | Venue | Link | What it shows | 中文要点 |
|---|---|---|---|---|---|
| ReAct: Synergizing Reasoning and Acting in Language Models | Yao, 2022 | ICLR 2023 | [2210.03629](https://arxiv.org/abs/2210.03629) | Interleaves reasoning and tool actions. | 推理和工具调用交替进行。交互式 Text-to-SQL 智能体的基础。 |
| OpenAI o1 System Card | OpenAI, 2024 | arXiv | [2412.16720](https://arxiv.org/abs/2412.16720) | System card for a model trained to reason at length before answering. | 先长时间推理再作答的模型的系统卡。 |
| DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning | DeepSeek-AI, 2025 | arXiv | [2501.12948](https://arxiv.org/abs/2501.12948) | RL with verifiable rewards produces long chain-of-thought reasoning. | 用可验证奖励的 RL 训练出长思维链推理。 |
| s1: Simple test-time scaling | Muennighoff, 2025 | arXiv | [2501.19393](https://arxiv.org/abs/2501.19393) | "Budget forcing" controls how long the model thinks. | 用"预算强制"控制思考长度。 |

---

## 2. Test-time compute in Text-to-SQL Text-to-SQL 中的测试时计算

### 2.1 Multiple candidates plus selection 多候选 + 挑选

| Paper | First author, year | Venue | Link | What it does | 中文要点 |
|---|---|---|---|---|---|
| DIN-SQL: Decomposed In-Context Learning of Text-to-SQL with Self-Correction | Pourreza, 2023 | NeurIPS 2023 | [2304.11015](https://arxiv.org/abs/2304.11015) | Decomposes the task into sub-steps and adds a self-correction step. | 把任务拆成子步骤，最后加自我修正。 |
| Text-to-SQL Empowered by Large Language Models: A Benchmark Evaluation (DAIL-SQL) | D. Gao, 2023 | arXiv | [2308.15363](https://arxiv.org/abs/2308.15363) | Prompt and example-selection study; uses self-consistency over execution results. | 系统比较提示与示例选择，并对执行结果做自洽投票。 |
| C3: Zero-shot Text-to-SQL with ChatGPT | Dong, 2023 | arXiv | [2307.07306](https://arxiv.org/abs/2307.07306) | Zero-shot pipeline with consistency-based output calibration. | 零样本流程，最后按一致性校准输出。 |
| MCS-SQL: Leveraging Multiple Prompts and Multiple-Choice Selection For Text-to-SQL Generation | D. Lee, 2024 | arXiv | [2405.07467](https://arxiv.org/abs/2405.07467) | Multiple prompts produce many candidates; confidence filtering, then the LLM picks via multiple choice. | 多提示生成大量候选，按置信度过滤后让 LLM 以选择题方式挑一个。 |
| CHASE-SQL: Multi-Path Reasoning and Preference Optimized Candidate Selection in Text-to-SQL | Pourreza, 2024 | arXiv | [2410.01943](https://arxiv.org/abs/2410.01943) | Several chain-of-thought generators plus a fine-tuned pairwise selection model. | 多种思维链生成器 + 微调的成对比较挑选模型。 |
| A Preview of XiYan-SQL: A Multi-Generator Ensemble Framework for Text-to-SQL | Y. Gao, 2024 | arXiv | [2411.08599](https://arxiv.org/abs/2411.08599) | Ensemble of several generators and a trained selector. | 多个生成器集成 + 训练好的挑选器。 |
| RSL-SQL: Robust Schema Linking in Text-to-SQL Generation | Cao, 2024 | arXiv | [2411.00073](https://arxiv.org/abs/2411.00073) | Bidirectional schema linking, binary selection between two strategies, multi-turn self-correction. Strict schema recall 94% with 83% fewer columns. | 双向模式链接（严格召回 94%、列数减少 83%）、两种策略二选一、多轮自我修正。 |
| GradeSQL: Test-Time Inference with Outcome Reward Models for Text-to-SQL Generation from LLMs | Tritto, 2025 | arXiv | [2509.01308](https://arxiv.org/abs/2509.01308) | Trains outcome reward models for SQL. Best-of-N with the ORM beats execution-based best-of-N by +4.33 (BIRD) and +2.10 (Spider), and majority voting by +2.91 and +0.93. | 训练 SQL 专用结果奖励模型；ORM 挑选比"能执行就选"高 4.33（BIRD）/2.10（Spider），比多数投票高 2.91/0.93。 |
| Test-Time Verification for Text-to-SQL via Outcome Reward Models | Tritto, 2026 | ACL 2026 workshop (SURGeLLM) | [2606.30851](https://arxiv.org/abs/2606.30851) | Workshop version of GradeSQL: labels from execution, no manual annotation; gains grow with candidate-set size and on complex queries. | GradeSQL 的研讨会版：用执行结果自动标注训练 ORM，候选越多、题越难增益越大。 |
| JudgeSQL: Reasoning over SQL Candidates with Weighted Consensus Tournament | Bai, 2025 | arXiv | [2510.15560](https://arxiv.org/abs/2510.15560) | Argues selection is the new bottleneck; RL-trained judge plus a weighted consensus tournament. | 认为测试时扩展后"挑选"成了瓶颈；用 RL 训练的判别模型 + 加权共识淘汰赛挑选。 |
| Agentar-Scale-SQL: Advancing Text-to-SQL through Orchestrated Test-Time Scaling | P. Wang, 2025 | arXiv | [2509.24403](https://arxiv.org/abs/2509.24403) | Combines internal scaling (RL reasoning), sequential scaling (refinement) and parallel scaling (diverse synthesis plus tournament selection). 81.67% EX on BIRD test, first on the leaderboard at publication. | 三种扩展组合：RL 内部推理、顺序修正、并行生成 + 淘汰赛挑选；BIRD 测试集 81.67%，发表时排行榜第一。 |
| Rethinking Agentic Workflows: Evaluating Inference-Based Test-Time Scaling Strategies in Text2SQL Tasks | J. Guo, 2025 | COLM 2025 workshop (SCALR) | [2510.10885](https://arxiv.org/abs/2510.10885) | Benchmarks six lightweight strategies with four LLMs on BIRD Mini-Dev, including latency and tokens. Divide-and-conquer prompting and few-shot help consistently; extra workflow steps give mixed results. | 在 BIRD Mini-Dev 上比较 6 种轻量策略、4 个模型，并报告延迟和 token；分治提示和少样本示例稳定有效，增加流程步骤效果不一。 |

### 2.2 Tree search for SQL SQL 树搜索

| Paper | First author, year | Venue | Link | What it does | 中文要点 |
|---|---|---|---|---|---|
| Alpha-SQL: Zero-Shot Text-to-SQL using Monte Carlo Tree Search | B. Li, 2025 | ICML 2025 | [2502.17248](https://arxiv.org/abs/2502.17248) | MCTS over seven reasoning actions, LLM as action model, self-consistency reward. BIRD dev 66.8 / 68.7 / 69.7 with Qwen2.5-Coder 7B / 14B / 32B, no fine-tuning. | 在 7 种推理动作上做 MCTS，奖励为执行结果自洽度；不微调，BIRD dev 7B/14B/32B 分别为 66.8/68.7/69.7。 |
| SQL-o1: A Self-Reward Heuristic Dynamic Search Method for Text-to-SQL | Lyu, 2025 | arXiv | [2502.11741](https://arxiv.org/abs/2502.11741) | Self-reward MCTS with dynamic pruning; +10.8 EX on BIRD. | 自我奖励的 MCTS + 动态剪枝，BIRD 上提升 10.8 EX。 |
| MCTS-SQL: Light-Weight LLMs can Master the Text-to-SQL through Monte Carlo Tree Search | S. Yuan, 2025 | AAAI 2026 | [2501.16607](https://arxiv.org/abs/2501.16607) | MCTS refinement for small models with a token-level prefix cache to cut cost; Qwen2.5-Coder-1.5B beats ChatGPT-3.5. | 面向小模型的 MCTS 修正，用前缀缓存降低成本；1.5B 模型超过 ChatGPT-3.5。 |
| IESR: Efficient MCTS-Based Modular Reasoning for Text-to-SQL with LLMs | T. Liu, 2026 | EMNLP 2026 | [2602.05385](https://arxiv.org/abs/2602.05385) | MCTS multi-path reasoning with majority voting plus a trajectory-consistency discriminator, for lightweight models. | 面向轻量模型：MCTS 多路径推理 + 多数投票 + 轨迹一致性判别器。 |

### 2.3 Reward models and RL reasoning for SQL SQL 奖励模型与 RL 推理

| Paper | First author, year | Venue | Link | What it does | 中文要点 |
|---|---|---|---|---|---|
| Reward-SQL: Boosting Text-to-SQL via Stepwise Execution-Aware Reasoning and Process-Supervised Rewards | Y. Zhang, 2025 | arXiv | [2505.04671](https://arxiv.org/abs/2505.04671) | Step-by-step CTE reasoning with a process reward model used in both RL training and inference. | 用 CTE 分步构造 SQL，过程奖励模型同时用于 RL 训练和推理时引导。 |
| Reasoning-SQL: Reinforcement Learning with SQL Tailored Partial Rewards | Pourreza, 2025 | arXiv | [2503.23157](https://arxiv.org/abs/2503.23157) | GRPO with several SQL-specific partial rewards in addition to execution correctness. | GRPO + 多种针对 SQL 的部分奖励（除执行正确外）。 |
| SQL-R1: Training Natural Language to SQL Reasoning Model By Reinforcement Learning | P. Ma, 2025 | NeurIPS 2025 | [2504.08600](https://arxiv.org/abs/2504.08600) | GRPO with layered rewards; self-consistency over 8 at inference. | 分层奖励的 GRPO，推理时 8 选 1 投票。（之前精读写成 arXiv 预印本，按 arXiv 记录已被 NeurIPS 2025 接收。） |
| Arctic-Text2SQL-R1: Simple Rewards, Strong Reasoning in Text-to-SQL | Yao, 2025 | arXiv | [2505.20315](https://arxiv.org/abs/2505.20315) | RL with a simple execution-based reward. | 只用简单的执行奖励做 RL。 |

### 2.4 Agentic exploration and adaptive cost 智能体探索与按难度分配

| Paper | First author, year | Venue | Link | What it does | 中文要点 |
|---|---|---|---|---|---|
| MAC-SQL: A Multi-Agent Collaborative Framework for Text-to-SQL | B. Wang, 2023 | COLING 2025 | [2312.11242](https://arxiv.org/abs/2312.11242) | Selector, decomposer and refiner agents; the refiner fixes SQL from execution errors. | 选择器、分解器、修正器三个智能体，修正器按执行报错改 SQL。 |
| CHESS: Contextual Harnessing for Efficient SQL Synthesis | Talaei, 2024 | arXiv | [2405.16755](https://arxiv.org/abs/2405.16755) | Multi-agent pipeline with database value retrieval and schema pruning before SQL generation. | 多智能体流程：先检索数据库中的值、剪枝模式，再生成 SQL。 |
| ReFoRCE: A Text-to-SQL Agent with Self-Refinement, Consensus Enforcement, and Column Exploration | Deng, 2025 | arXiv | [2502.00675](https://arxiv.org/abs/2502.00675) | Spider 2.0 agent: schema compression, self-refinement across dialects, majority-vote consensus, iterative column exploration; topped the Spider 2.0 leaderboard. | Spider 2.0 智能体：压缩模式、跨方言自我修正、多数投票、迭代探索列；曾登顶 Spider 2.0 榜单。 |
| RAISE: Reasoning Agent for Interactive SQL Exploration | Granado, 2025 | arXiv | [2506.01273](https://arxiv.org/abs/2506.01273) | Scales test-time compute by the depth of interactive database exploration. BIRD EX 44.8 → 56.5 with DeepSeek-R1-Distill-Llama-70B; best-of-N 81.8 with 8 rounds. | 把测试时计算花在"与数据库交互探索的深度"上；BIRD 从 44.8 提到 56.5，8 轮候选的 best-of-N 达 81.8。 |
| EllieSQL: Cost-Efficient Text-to-SQL with Complexity-Aware Routing | Y. Zhu, 2025 | COLM 2025 | [2503.22402](https://arxiv.org/abs/2503.22402) | Routes each query to a cheap or expensive pipeline by estimated complexity; over 40% fewer tokens with no accuracy loss on BIRD dev. | 按估计复杂度把题分配给便宜或昂贵的流程；BIRD dev 上 token 减少 40% 以上而准确率不降。 |

### 2.5 Amortizing search into the model: closest to our project 把搜索摊销进模型：与我们最接近

Reviewers will compare our work with these papers, so all of them should be cited. 审稿人一定会拿这些和我们比较，必须引用并讨论差异。

| Paper | First author, year | Venue | Link | What it does | Relation to us 与我们的关系 |
|---|---|---|---|---|---|
| STaR-SQL: Self-Taught Reasoner for Text-to-SQL | He, 2025 | arXiv | [2502.13550](https://arxiv.org/abs/2502.13550) | STaR on Text-to-SQL: fine-tune on rationales that reach correct SQL, then add an outcome reward model as verifier. Spider EX 86.6. | 就是 Text-to-SQL 上的 STaR 自训练，与我们的设定最接近；它只看能不能提分，没有比较"留哪些正确样本"，也没有测多轮效用和覆盖率。 |
| SQLConductor: Search-to-Policy Learning for Step-wise Text-to-SQL Orchestration | Y. Zhu, 2026 | arXiv | [2606.23537](https://arxiv.org/abs/2606.23537) | MCTS explores candidate workflows; stability-weighted SFT plus curriculum RL turns the search into a policy. 73.2% EX on BIRD dev. | "搜索→策略"的摊销：用 MCTS 找好流程再训练进模型。它按"稳定性"给样本加权，相当于一种选样规则，可作对照。 |
| From Test-Time Scaling to Reusable Memory: Measuring Crystallization in Text-to-SQL | J. Wang, 2026 | arXiv | [2608.07213](https://arxiv.org/abs/2608.07213) | Defines measuring the future value of test-time repairs as the "crystallization problem". On BIRD, storing verified corrected queries as memory raises held-out first-attempt accuracy by 4.34 points, capturing 44.4% of the headroom from on-demand repair. | 问题框架与我们非常像（测试时修正的"未来价值"），但它存进检索记忆，不训练模型参数；可作为"记忆 vs 训练"的对照。 |
| SERL-SQL: Selective Hindsight Distillation for Text-to-SQL Reinforcement Agentic Learning | T. Liu, 2026 | arXiv (under review) | [2608.00485](https://arxiv.org/abs/2608.00485) | Multi-turn SQL agent trained with GRPO; a training-only teacher re-scores actions to give token-level credit. 76.56 BIRD dev, 89.92 Spider test; reward-based selection approaches the oracle best-of-N. | 多轮执行反馈的 RL 智能体；在"哪一步该得功劳"上做细，和我们"哪些轨迹该被训练"是互补的问题。 |
| rStar-Math (above) and ReST-MCTS* (above) | – | – | – | Multi-round search-then-train in math. | 数学上的多轮"搜索→训练"，是我们在方法层面的最近邻。 |

---

## 3. Multi-turn Text-to-SQL 多轮 Text-to-SQL

### 3.1 Conversational (context-dependent) datasets 对话式（依赖上下文）数据集

| Paper | First author, year | Venue | Link | What it is | 中文要点 |
|---|---|---|---|---|---|
| SParC: Cross-Domain Semantic Parsing in Context | T. Yu, 2019 | ACL 2019 | [1906.02285](https://arxiv.org/abs/1906.02285) | 4,298 coherent question sequences (12k+ questions with SQL) over 200 databases in 138 domains. Best baseline at release: 20.2% exact match over questions, under 10% over whole sequences. | 4,298 个连贯问题序列（1.2 万+ 个带 SQL 的问题）；发布时最好模型逐题 20.2%，整段对话不到 10%。 |
| CoSQL: A Conversational Text-to-SQL Challenge Towards Cross-Domain Natural Language Interfaces to Databases | T. Yu, 2019 | EMNLP 2019 | [1909.05378](https://arxiv.org/abs/1909.05378) | 3k Wizard-of-Oz dialogues, 30k+ turns, 10k+ SQL queries; the expert also clarifies ambiguous questions and flags unanswerable ones. | 3 千段人工模拟对话、3 万+ 轮、1 万+ 条 SQL；专家会澄清歧义问题、说明无法回答的问题。 |
| PRACTIQ: A Practical Conversational Text-to-SQL dataset with Ambiguous and Unanswerable Queries | Dong, 2024 | arXiv | [2410.11076](https://arxiv.org/abs/2410.11076) | Four-turn conversations around four types of ambiguous and four types of unanswerable questions. | 围绕 4 类歧义问题和 4 类无法回答问题构造 4 轮对话。 |

### 3.2 Conversational methods 对话式方法

| Paper | First author, year | Venue | Link | Idea | 中文要点 |
|---|---|---|---|---|---|
| Editing-Based SQL Query Generation for Cross-Domain Context-Dependent Questions (EditSQL) | R. Zhang, 2019 | EMNLP 2019 | [1909.00786](https://arxiv.org/abs/1909.00786) | Generate the current SQL by editing the previous one. | 在上一轮 SQL 上修改出这一轮的 SQL。 |
| IGSQL: Database Schema Interaction Graph Based Neural Model for Context-Dependent Text-to-SQL Generation | Cai, 2020 | EMNLP 2020 | [2011.05744](https://arxiv.org/abs/2011.05744) | Graph over schema items used across turns. | 用跨轮的模式交互图建模上下文。 |
| Tracking Interaction States for Multi-Turn Text-to-SQL Semantic Parsing | R.-Z. Wang, 2020 | AAAI 2021 | [2012.04995](https://arxiv.org/abs/2012.04995) | Tracks schema and SQL states across turns. | 跨轮追踪模式状态和 SQL 状态。 |
| Decoupled Dialogue Modeling and Semantic Parsing for Multi-Turn Text-to-SQL | Z. Chen, 2021 | Findings of ACL 2021 | [2106.02282](https://arxiv.org/abs/2106.02282) | Rewrite each utterance into a standalone question, then use a single-turn parser. | 先把每轮问题改写成独立问题，再用单轮解析器。 |
| HIE-SQL: History Information Enhanced Network for Context-Dependent Text-to-SQL Semantic Parsing | Zheng, 2022 | Findings of ACL 2022 | [2203.07376](https://arxiv.org/abs/2203.07376) | Uses both history utterances and the last predicted SQL. | 同时利用历史问题和上一轮预测的 SQL。 |
| CQR-SQL: Conversational Question Reformulation Enhanced Context-Dependent Text-to-SQL Parsers | Xiao, 2022 | Findings of EMNLP 2022 | [2205.07686](https://arxiv.org/abs/2205.07686) | Question reformulation as an auxiliary signal. | 用问题改写作辅助信号。 |
| RASAT: Integrating Relational Structures into Pretrained Seq2Seq Model for Text-to-SQL | Qi, 2022 | EMNLP 2022 | [2205.06983](https://arxiv.org/abs/2205.06983) | Relation-aware T5; also evaluated on SParC and CoSQL. | 关系感知的 T5，在 SParC/CoSQL 上也有结果。 |
| STAR: SQL Guided Pre-Training for Context-dependent Text-to-SQL Parsing | Cai, 2022 | EMNLP 2022 | [2210.11888](https://arxiv.org/abs/2210.11888) | Pre-training objectives guided by SQL for conversational parsing. | 针对对话式解析、用 SQL 引导的预训练。 |
| QURG: Question Rewriting Guided Context-Dependent Text-to-SQL Semantic Parsing | Chai, 2023 | arXiv | [2305.06655](https://arxiv.org/abs/2305.06655) | Rewriting edit matrix fed into a two-stream encoder. | 用问题改写的编辑矩阵辅助编码。 |
| Conversational Text-to-SQL: An Odyssey into State-of-the-Art and Challenges Ahead | Parthasarathi, 2023 | ICASSP 2023 | [2302.11054](https://arxiv.org/abs/2302.11054) | Multi-task T5 plus n-best reranking on CoSQL; context-dependent turns are much harder. | CoSQL 上的多任务 T5 + n-best 重排；依赖上下文的轮次明显更难。 |
| CoE-SQL: In-Context Learning for Multi-Turn Text-to-SQL with Chain-of-Editions | H. Zhang, 2024 | arXiv | [2405.02712](https://arxiv.org/abs/2405.02712) | Prompts the LLM to edit the previous SQL through an edit chain; state of the art among ICL methods on SParC and CoSQL. | 提示 LLM 通过"编辑链"修改上一轮 SQL；在 SParC/CoSQL 上是 ICL 方法中最好的。 |
| QDA-SQL: Questions Enhanced Dialogue Augmentation for Multi-Turn Text-to-SQL | Y. Sun, 2024 | CICAI 2026 | [2406.10593](https://arxiv.org/abs/2406.10593) | LLM-generated multi-turn data, including ambiguous and unanswerable turns, with validation and correction. | 用 LLM 生成含歧义/无法回答问题的多轮训练数据，并带校验修正。 |
| Rose-SQL: Role-State Evolution Guided Structured Reasoning for Multi-Turn Text-to-SQL | L. Zhou, 2026 | arXiv | [2605.03720](https://arxiv.org/abs/2605.03720) | Training-free; small reasoning models track a "Role-State" blueprint across turns. | 免训练：小推理模型跨轮追踪"角色状态"蓝图。 |

### 3.3 Interactive / agentic multi-turn 交互式 / 智能体式多轮

| Paper | First author, year | Venue | Link | What it is | 中文要点 |
|---|---|---|---|---|---|
| InterCode: Standardizing and Benchmarking Interactive Coding with Execution Feedback | J. Yang, 2023 | arXiv | [2306.14898](https://arxiv.org/abs/2306.14898) | Interactive coding as an RL environment: code is the action, execution feedback the observation. Includes an SQL environment built from Spider. | 把交互式编程做成强化学习环境：代码是动作、执行反馈是观察；含基于 Spider 的 SQL 环境。是"多轮执行反馈"最直接的引用。 |
| AgentBench: Evaluating LLMs as Agents | X. Liu, 2023 | ICLR 2024 | [2308.03688](https://arxiv.org/abs/2308.03688) | Agent benchmark that includes a database-operation environment. | 智能体评测基准，包含数据库操作环境。 |
| Spider 2.0: Evaluating Language Models on Real-World Enterprise Text-to-SQL Workflows | Lei, 2024 | arXiv | [2411.07763](https://arxiv.org/abs/2411.07763) | 632 enterprise workflow problems on BigQuery, Snowflake and others, often with 1,000+ columns. Their o1-preview-based code agent solves 21.3%, versus 91.2% on Spider 1.0 and 73.0% on BIRD. | 632 个企业级工作流问题；基于 o1-preview 的智能体只解出 21.3%（Spider 1.0 为 91.2%，BIRD 为 73.0%）。 |
| BIRD-INTERACT: Re-imagining Text-to-SQL Evaluation for LLMs via Lens of Dynamic Interactions | Huo, 2025 | ICLR 2026 (Oral) | [2510.05318](https://arxiv.org/abs/2510.05318) | Each database has a knowledge base and a user simulator; c-Interact (fixed protocol) and a-Interact (agent decides when to ask or explore); full CRUD tasks. GPT-5 completes 8.67% (c-Interact) and 17.00% (a-Interact). | 每个库配知识库和用户模拟器；两种设定：固定对话协议和智能体自主决定何时提问或探索；覆盖增删改查。GPT-5 只完成 8.67%/17.00%。由 BIRD 团队发布，与我们最相关的多轮基准。 |
| Interactive Text-to-SQL via Expected Information Gain for Disambiguation | Qiu, 2025 | arXiv | [2507.06467](https://arxiv.org/abs/2507.06467) | Asks clarifying questions chosen by expected information gain. | 按期望信息增益选择要向用户澄清的问题。 |
| MTSQL-R1: Towards Long-Horizon Multi-Turn Text-to-SQL via Agentic Training | T. Guo, 2025 | ACL 2026 (Main) | [2510.12831](https://arxiv.org/abs/2510.12831) | Treats conversational Text-to-SQL as an MDP: the agent executes against the database and checks a dialogue memory in a propose → execute → verify → refine loop. Beats strong baselines on CoSQL and SParC. | 把对话式任务当作 MDP：智能体与数据库交互获取执行反馈、对照对话记忆检查一致性，循环"提出→执行→验证→修改"；在 CoSQL/SParC 上超过强基线。正好把两种"多轮"结合起来。 |
| Memory Architectures for Multi-Turn Text-to-SQL: A Benchmark and Empirical Study | Tummalapenta, 2026 | arXiv | [2605.26394](https://arxiv.org/abs/2605.26394) | EnterpriseMem-Bench (300 sessions, 1,400 turns). Stateless multi-turn Text-to-SQL falls to zero EX by turn 3 for all five frontier models tested. | 企业多轮基准；不带记忆的多轮 Text-to-SQL 到第 3 轮时所有模型准确率都降为 0。 |

---

## 4. Corrections to the earlier tab 对之前 tab 内容的修正

- SQL-R1 venue: the arXiv record says NeurIPS 2025, not "arXiv preprint". SQL-R1 发表于 NeurIPS 2025。
- Spider 2.0 headline: the o1-preview-based agent solves 21.3% of tasks (the earlier tab said "about one fifth"; the exact figure is 21.3%). Spider 2.0 准确数字为 21.3%。
- "Spider-Agent" is the code-agent framework released with Spider 2.0. Cite the Spider 2.0 paper (2411.07763); there is no separate paper. Spider-Agent 应引用 Spider 2.0 原文。
- MAC-SQL: COLING 2025. MCTS-SQL: AAAI 2026. XiYan-SQL's arXiv title is "A Preview of XiYan-SQL". 补充会议信息与准确标题。
- The CHASE (Chinese) conversational dataset is not on arXiv and could not be verified this way; it is left out here. 中文 CHASE 数据集不在 arXiv 上，未能核实，暂不列入。
- New work the earlier tab missed and that reviewers will expect: STaR-SQL, SQLConductor, the crystallization paper, SERL-SQL, GradeSQL, JudgeSQL, Agentar-Scale-SQL, BIRD-INTERACT, MTSQL-R1, InterCode. 之前遗漏的、审稿人会期待看到的新工作见上表。
