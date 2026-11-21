# LSE 实验：复现与“逐库进化”协议下的递归自我改进

对应文献精读页 LSE 标签页的“E 实验指南”（下文的 E.x 均指该指南）。
上游代码：<https://github.com/chenyn66/learning-to-self-evolve>，固定在提交 `9eb5eac`（2026-06-18）。

## 目录

```
experiments/lse/
  README.md                 本文件
  setup.sh                  克隆上游到 third_party/（固定提交）、安装环境、下载 BIRD 数据库
  configs/replication.yaml  第一阶段（复现，E.4 的 R1）的设置：库、种子、论文参数、对照数字
  lse_rsi/                  我们自己的代码；不修改上游，只调用或子类化
    paths.py                定位上游仓库与默认目录
    run.py                  单次运行入口：照上游 main.py 构造模拟器，并把全部指标另存为 JSONL
    results.py              从运行目录读出成绩（tree.json、指标 JSONL、result.json）
  scripts/
    serve_model.sh          自建 vLLM OpenAI 兼容服务（小显存份额，适合共享 GPU）
    run_replication.py      按配置批量运行 R1（可续跑、可只打印命令）
    summarize.py            汇总复现结果，与论文 Table 1 对照
    check_dev_version.py    逐题比对两份 BIRD dev 的标准 SQL（E.3：dev 版本必须一致）
  tests/                    CPU 上可跑的单元测试（只测解析与比对逻辑，不调用模型）
  third_party/              setup.sh 生成，上游代码，不手改
  runs/                     运行输出（默认位置，可用 --log-root 改）
```

## 进度

| 阶段 | 内容 | 状态 |
|---|---|---|
| 第一阶段 | E.8 步骤 0–2：环境、冒烟测试、复现 R1-0 / R1-a / R1-b / R1-c | 环境与冒烟测试已在 liu01s 通过（2026-11-17）；复现进行中 |
| 第二阶段 | E.6 的改动：反馈档位、剪枝门槛、元步骤（L3）、CMP 选择、模板迁移、逐题结果与重新评估脚本 | 未开始 |
| 第三阶段 | 预实验、主实验、反馈强度、选择规则与迁移（E.8 步骤 3–7） | 未开始 |

第一阶段不改动上游的任何逻辑：`lse_rsi/run.py` 只做两件事——按上游 `main.py` 的方式构造模拟器；把 `logger.log` 记录的指标同时写入运行目录下的 `rsi_metrics.jsonl`（上游只写 wandb 的二进制离线文件，TextGrad 的留出集成绩只在那里）。

## 运行环境

- **Linux**。上游 `lse/agents/base.py` 在文件开头就导入 vLLM 与 torch，即使走接口也必须能导入（E.2）。macOS 上只能跑 `tests/` 和 `scripts/check_dev_version.py`。
- **模型**：`Qwen/Qwen3-4B-Instruct-2507`。两种方式二选一：
  - 本地 vLLM（需要 GPU）：不设置 `LSE_MODEL_URL`。
  - OpenAI 兼容接口：设置 `LSE_MODEL_URL`；密钥放在环境变量 `OPENAI_API_KEY`，**不要**写进命令行参数，否则会被上游写进 `env/config.yaml` 与 wandb 配置。
- **数据**：上游自带 BIRD dev 的题目文件（1,534 题、11 个库）与训练子集题目（4,161 题、27 个库）；数据库文件由 `setup.sh` 用上游脚本下载。注意：上游下载 dev 数据库用的是官方 Mini-Dev 压缩包（`minidev.zip`）里的 `dev_databases`，题目仍是完整 dev；这可能就是论文写“Mini-Dev”的原因（见 E.3）。

## 服务器记录（engr-liu01s）

- 硬件：1 张 H100 PCIe 80 GB，与其他用户共享（2026-11-17 时另有实验占约 41.6 GB、利用率 100%）；根分区几乎已满，`TMPDIR`、`HF_HOME`、`UV_CACHE_DIR` 一律指向家目录。
- **dev 版本已核对（2026-11-17）**：上游自带的 `dev.json` 与服务器上 `~/RSI-Text-to-SQL/data/bird_dev/dev_20240627/dev.json` 逐题比对，1,534 题的库名、题目、evidence、标准 SQL 完全一致（`runs/dev_version_diff.json`）。因此不下载 Mini-Dev 压缩包，数据库直接用同一份 dev_20240627：`export BIRD_DB_ROOT_DEV=~/RSI-Text-to-SQL/data/bird_dev/dev_20240627/dev_databases`，与 RoboPhD 实验完全相同。
- 模型：上游本地 vLLM 模式写死占用 80% 显存、张量并行数等于 GPU 数，在共享 GPU 上会失败；改为 `scripts/serve_model.sh` 自建 OpenAI 兼容服务（默认只占 30% 显存），上游走接口模式。
- 环境（2026-11-17）：torch 2.8.0+cu128、vLLM 0.11.0，H100 可用；服务器上 62 个测试全部通过（含对上游真实配置的组装测试）。模型服务常驻在 tmux 会话 `lse-vllm`，KV 缓存 4,744 块（约 7.6 万 token）。
- 冒烟测试（financial，2 轮，每轮 2 题，留出 4 题 × 生成 2 次）：通过，用时 257 秒。种子指令留出集 0.375，第 1 轮新指令 0.5；`tree.json` 与另存指标交叉核对一致。
- **服务崩溃与修复（2026-11-17）**：第一个正式运行（financial，种子 1）跑到第 7 轮时，模型服务在 KV 缓存 100%、约 150 个请求并发的状态下报 “CUDA error: an illegal memory access” 并退出（vLLM 0.11 引擎层故障；日志存为 `runs/vllm_server.crash-20261117.log`），该运行失败。修复：显存份额 0.30 → 0.40（KV 缓存约 7.6 万 → 16.9 万 token），并加 `--max-num-seqs 96`；模型服务用 `RESTART=1` 退出后自动重启；`run_replication.py` 每个运行前先等服务可用，失败的运行把旧目录存档为 `<名称>.attempt-<时间>` 后从头重跑一次，服务长时间不可用时停止整批而不是让后续运行全部失败。
- **观察**：Qwen3-4B 作改进器时，把整段系统提示（含数据库 schema）都写进了新 instruction，长度从 72 字符涨到 7,230 字符。这是上游加该模型的行为，不是我们的改动；复现时要逐轮记录 instruction 长度，并与论文附录 B.3 那种简洁规则清单对照。

## 步骤

```bash
cd experiments/lse

# 0. 环境与数据（Linux）
SKIP_DATA=1 bash setup.sh          # 克隆上游@9eb5eac、安装上游环境（数据库用现成的 dev_20240627，见上）
source third_party/learning-to-self-evolve/.venv/bin/activate
export PYTHONPATH="$PWD:${PYTHONPATH:-}"
export BIRD_DB_ROOT_DEV=~/RSI-Text-to-SQL/data/bird_dev/dev_20240627/dev_databases

# 0a. 模型服务（另开一个 tmux 窗口，常驻）
bash scripts/serve_model.sh        # GPU=0 MEM=0.30 PORT=8011 可改
export LSE_MODEL_URL=http://127.0.0.1:8011/v1
export OPENAI_API_KEY=EMPTY        # 本地服务不校验密钥，但 OpenAI 客户端要求非空

# 0b. dev 版本核对（E.3）：与 RoboPhD 使用的 dev_20240627 逐题比对
python scripts/check_dev_version.py \
  --a third_party/learning-to-self-evolve/data/bird/dev_data/dev.json \
  --b <BIRD dev_20240627 的 dev.json> --out runs/dev_version_diff.json

# 1. 冒烟测试：1 个库、2 轮、每轮 2 题、留出 4 题
python scripts/run_replication.py --smoke

# 2. 复现 R1：先只打印命令检查，再正式运行（可中断，重跑时跳过已完成的运行）
python scripts/run_replication.py --dry-run
python scripts/run_replication.py
python scripts/summarize.py        # -> runs/replication_summary.md
```

## 复现的通过标准（E.7）

- 论文的报告方式：每个库取 25 轮中留出集的最好成绩，再对 5 个库取平均；每个方法至少 3 个种子，报告均值与范围。
- R1-0（种子指令）对照 57.2，R1-a（未训练改进器）对照 62.2，GEPA 对照 62.8，TextGrad 对照 63.1。
- 要求未训练改进器相对种子的提升方向一致、幅度在论文 5.0 个点的合理范围内；论文没有给出多次运行的波动，所以不要求逐点吻合。
- GEPA 在留出集上每题只生成 1 次，LSE 是 8 次（E.3），两者的复现数字不是同一口径，只与论文各自的数字对照。

## 不在这里做的

- RL 训练出来的 LSE 改进器（论文 67.3）：不复现，只作参考上界。
- 任何会修改上游行为的改动：放在第二阶段，以子类或单独模块的形式写在 `lse_rsi/` 中，并在这里登记。
