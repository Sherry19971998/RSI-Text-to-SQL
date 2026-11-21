"""Build the Chinese group-meeting deck: main comparison (12) + per-paper appendix + references."""
import json
import os
import sys

from pptx import Presentation
from pptx.util import Inches

sys.path.insert(0, os.path.dirname(__file__))
import lib
from lib import (BLUE, CARD, GRAY, LGRAY, NAVY, ORANGE, WHITE, add_formula, arrow, footer, grid,
                 hline, notes, rect, text, title_band)

OUT_DIR = sys.argv[1]
META = json.load(open(sys.argv[2]))
lib.FORMULA_DIR = os.path.join(sys.argv[3])
os.makedirs(lib.FORMULA_DIR, exist_ok=True)


def B(t, **o):
    return (t, dict(bold=True, **o))


def N(t, **o):
    return (t, dict(o))


def O(t, **o):
    return (t, dict(color=ORANGE, **o))


def G(t, **o):
    return (t, dict(color=GRAY, **o))


AN = G("〔分析〕")      # our analysis, not the paper's claim
TBC = O("〔待核实〕")


def bl(*runs):
    return {"runs": list(runs), "bullet": True}


prs = Presentation()
prs.slide_width = Inches(lib.SW)
prs.slide_height = Inches(lib.SH)
BLANK = prs.slide_layouts[6]
SLIDES = []          # (slide, source, notes)
LINKS = []           # (shape, key) -> appendix slide for key
APPX = {}            # key -> first appendix slide
DETAILS = []        # formula material kept separate from the method/evidence pages
NAV = []            # (shape, target slide), resolved after the directory is filled
MAIN_ORIGIN = {"alpha": 6, "csc": 7, "r3": 7, "dysql": 9, "birdint": 9}


def new(title=None, tag=None):
    s = prs.slides.add_slide(BLANK)
    bg = s.background.fill
    bg.solid()
    bg.fore_color.rgb = lib.rgb(WHITE)
    if title:
        title_band(s, title, tag)
    return s


def strip_check(yy, h):
    if yy + 0.16 + h > 6.97:
        lib.WARN.append(f"STRIP past footer: bottom={yy + 0.16 + h:.2f}")


def finish(s, src, note):
    SLIDES.append((s, src, note))


COLW = [1.45, 1.75, 2.5, 2.85, 1.88, 1.9]
HDR = ["论文", "解决什么问题", "主要贡献与关键步骤", "核心公式与说明", "优势与比较对象", "局限与适用边界"]


def paper_cell(name, sub, key=None, domain=None):
    runs = [[B(name, size=12)], [G(sub, size=10)]]
    if domain:
        runs.append([O(domain, size=9.5)])
    if key:
        runs.append([O("→ 详解", size=10)])
    return runs


# ---------------------------------------------------------------- 1 title
s = new()
rect(s, 0, 0, lib.SW, 3.35, fill=NAVY)
text(s, 0.7, 0.75, 11.9, 1.5, [[B("交互式 Text-to-SQL 的递归自训练")], [N("从交互轨迹选择到跨轮长期效用")]],
     size=34, color=WHITE, line=1.05, space_after=6)
text(s, 0.7, 2.55, 11.9, 0.5, [[N("组会汇报 · 2026-10-30 · RSI Text-to-SQL 项目")]], size=15, color="D5D8DE")
text(s, 0.7, 3.65, 5.6, 0.45, [[B("本次回答四个问题")]], size=17)
text(s, 0.7, 4.12, 5.9, 2.6, [
    [N("1. 这个领域在解决什么问题？")],
    [N("2. 已有方法分别怎么做，优缺点是什么？")],
    [N("3. 现有证据还回答不了哪些问题？")],
    [N("4. 我们准备研究什么，怎样验证？")],
], size=15, space_after=8)
rect(s, 7.0, 3.7, 5.83, 3.05, fill=CARD, rounded=True)
text(s, 7.2, 3.8, 5.45, 2.9, [
    [B("覆盖范围")],
    bl(N("通用测试时计算：作为方法背景")),
    bl(N("交互依据：BIRD-INTERACT、MTSQL-R1、SQLConductor")),
    bl(N("RSI 主线：新模型产生新轨迹，比较即时与长期效用")),
    bl(N("正文 13 页：文献比较 → 综合问题 → idea → 研究定位 → 验证")),
    bl(N("附录：方法流程与实验证据 → 公式专页 → 参考文献")),
    [G("文献比较与研究计划；不含本项目实验结果。", size=12)],
], size=13.5, space_after=6)
finish(s, None, """开场。今天这次组会想回答四个问题：这个方向解决什么问题；已有方法怎么做、各自的优缺点；现有证据还回答不了什么；以及我们准备研究什么、怎么验证。
范围上，我先用 7 篇代表论文讲清楚通用的“测试时计算”有哪几类做法，然后看它们在 Text-to-SQL 上的三种落地：Alpha-SQL、CSC-SQL、R³-SQL，再讲多轮 Text-to-SQL 和普通单轮有什么不同，用 DySQL-Bench 和 BIRD-INTERACT 两个基准来说明。
正文 13 页按背景、分类比较、综合问题、idea、研究定位与验证计划展开。附录 A 是 5 篇重点论文，每篇先看方法流程、再看实验证据；附录 B 分开列步骤、公式、符号与教学演算，最后是参考文献，目录可点击跳转。需要说明的是，这份材料只讲研究计划，不放我们已有的实验结果。""")

# ---------------------------------------------------------------- 2 concepts
s = new("背景：Text-to-SQL 与测试时计算", "背景")
flow = [("自然语言问题\n＋数据库结构", 0.5), ("大语言模型", 2.85), ("一条 SQL", 5.2), ("在数据库上执行", 7.55), ("与标准答案的\n执行结果比较", 9.9)]
for i, (t, x) in enumerate(flow):
    rect(s, x, 1.2, 2.0, 0.9, fill=CARD if i not in (4,) else "FBE9DF", rounded=True)
    text(s, x, 1.2, 2.0, 0.9, [[N(t)]], size=13, align="c", anchor="m", space_after=0)
    if i < 4:
        arrow(s, x + 2.05, 1.52, 0.28, 0.26)
text(s, 11.95, 1.2, 0.9, 0.9, [[B("EX", color=ORANGE)]], size=18, align="c", anchor="m")
cards = [
    ("Text-to-SQL（文本转 SQL）", "把用户用自然语言提的问题，翻译成能在数据库上运行的 SQL 查询。BIRD 开发集有 1,534 题，是本领域最常用的评测之一。"),
    ("执行准确率（Execution Accuracy, EX）", "预测 SQL 与标准 SQL 在数据库上执行结果相同的题目比例。只看结果是否一致，不看写法是否一样。"),
    ("测试时计算（test-time compute）", "模型参数不变，回答时多花计算：多采样几次、检查、修改，或者搜索。代价是每道题的推理成本上升。"),
    ("候选生成与选择（generate & select）", "先生成多个候选答案，决定可达到的准确率上限；再从中挑一个，决定能否选中正确答案。两步各有瓶颈。"),
    ("覆盖率（coverage，常用 pass@k 衡量）", "每题尝试 k 次、至少一次答对的题目比例。它是仅从当前候选池选择答案时的理想上限；新增或修正候选可改变上限。"),
    ("多轮（multi-turn）", "用户多轮对话与工具多步调用需分开：前者涉及澄清或追问，后者可用于单轮任务的执行与修正。"),
]
for i, (h, b) in enumerate(cards):
    cx = 0.5 + (i % 3) * 4.14
    cy = 2.5 + (i // 3) * 2.2
    rect(s, cx, cy, 3.95, 2.0, fill=CARD, rounded=True)
    text(s, cx + 0.12, cy + 0.1, 3.7, 0.5, [[B(h)]], size=13, space_after=0)
    text(s, cx + 0.12, cy + 0.58, 3.7, 1.36, [[N(b)]], size=12.5, line=1.15)
finish(s, "BIRD：Li et al. (2023)；pass@k 定义见 Chen et al. (2021)、Brown et al. (2024)",
       """先把几个术语讲清楚。Text-to-SQL 就是把一句自然语言问题变成 SQL。最常用的评分叫执行准确率，简称 EX：把预测的 SQL 和标准 SQL 都在数据库上跑一遍，结果一样就算对，写法不同没关系。
测试时计算，是指不改模型参数，只在回答的时候多花算力，比如多采样几次、让模型检查和修改、或者做搜索。
后面会反复用到两个概念。第一是“候选与挑选”：生成多个候选决定了最多能答对多少，挑选决定能不能真的选中对的那个。第二是覆盖率：每题试 k 次至少一次对的比例，它是从当前候选池选出正确答案的理想上限；若后续再生成或修正答案，这个上限也可能变化。最后，“多轮”在这个领域有两种意思，后面第 8 页专门讲。""")

# ---------------------------------------------------------------- 3 taxonomy
s = new("测试时计算怎么用？通用方法与 SQL 工作分开看", "方法背景")
text(s, 0.5, 1.1, 12.33, 0.63, [
    [B("先理解概念："), N("模型参数不变，同一道题多花回答时的计算：多试、打分、修改或搜索。")],
    [O("下面是通用方法背景，原论文的实验并非 Text-to-SQL；效果不能直接当作 SQL 证据。", size=12)],
], size=14, space_after=3)
rows = [
    ("并行采样", "多生成几个答案，再投票或验证", "Self-Consistency；Large Language Monkeys", "算术 / 常识；代码 / 数学 / 证明"),
    ("验证器", "给多个候选打分，再选一个", "Let's Verify Step by Step", "数学推理（MATH）"),
    ("顺序修正", "先写一版，再根据反馈修改", "Self-Refine；Huang 等（负面证据）", "多类生成、代码与推理；问答推理"),
    ("计算分配", "决定一题多试几次、用哪种策略", "Snell 等（计算最优策略）", "数学推理（MATH）"),
    ("树搜索", "分支尝试下一步，评估后再继续", "rStar", "数学与常识推理"),
]
grid(s, 0.5, 1.93, [1.7, 3.2, 4.35, 3.08], ["方法", "一句话解释", "通用代表论文", "原论文任务领域"],
     [[[[B(a)]], [[N(b)]], [[N(c)]], [[N(d)]]] for a,b,c,d in rows], 0.7, size=11, hsize=12)
rect(s, 0.5, 6.02, 12.33, 0.86, fill="FBE9DF", rounded=True)
text(s, 0.65, 6.08, 12.03, 0.75, [
    [B("SQL 专门工作："), N("Alpha-SQL＝SQL 动作搜索；CSC-SQL＝合并修正；R³-SQL＝重采样与组级排序。", size=12)],
    [G("阅读顺序：第 4–5 页讲通用背景；第 6 页对照 rStar 与 Alpha-SQL；第 7 页讲 SQL 候选选择。", size=11.5)],
], size=12, space_after=4)
finish(s, "原任务领域据各论文实验部分；分类为本次整理。通用推理结论不直接作为 SQL 实验证据",
       "本页先解释测试时计算，再区分通用方法与 SQL 专门研究。表中七篇为通用背景，原论文任务包括数学、常识、代码和生成等；SQL 专门研究是 Alpha-SQL、CSC-SQL 与 R³-SQL，详见第 6–7 页。")

# ---------------------------------------------------------------- 4 parallel + selection
s = new("通用文献背景 1｜并行采样与验证", "非 SQL 实验")
r_sc = [paper_cell("Self-Consistency", "Wang et al., ICLR 2023", domain="算术 / 常识，非 SQL"),
        [[N("贪心解码只保留一条推理路径，难以利用多种推理路径之间的共识。")]],
        [[N("① 用思维链提示采样多条推理路径（论文用 40 条）；② 只取每条的最终答案；③ 投票，选出现次数最多的答案。")]],
        dict(tex=r"\hat{a}=\arg\max_{a}\sum_{i=1}^{m}\mathbb{1}(a_i=a)", paras=[[G("对作者答案边缘化规则的计数化概括。", size=10.5), N("a_i：第 i 个样本的答案；m：样本数。出现最多的答案胜出。")]]),
        [[N("相对贪心解码：PaLM-540B 在 GSM8K 上 56.5→74.4（+17.9），无需训练。")]],
        [[N("相对带验证器的挑选：只能选最常见答案，少见但正确的答案会被投掉；成本随样本数线性增长。")]]]
r_mk = [paper_cell("Large Language Monkeys", "Brown et al., 2024, arXiv", domain="代码 / 数学 / 证明，非 SQL"),
        [[N("推理时通常只试一次；多次尝试能带来多少收益、规律如何，并不清楚。")]],
        [[N("① 每题重复采样，最多上万次；② 用覆盖率衡量；③ 比较自动验证（单测、证明检查）与投票、奖励模型。")]],
        dict(tex=r"\mathrm{pass}@k=\frac{1}{P}\sum_{i=1}^{P}\left[1-\frac{\binom{N-C_i}{k}}{\binom{N}{k}}\right]",
             paras=[[G("沿用 Chen et al. (2021) 的无偏估计，记号统一。", size=10.5), N("第 i 题采 N 次、对 C_i 次；括号内是“随机抽 k 个至少一个对”的概率。")]]),
        [[N("相对单次采样：SWE-bench Lite 上 15.9%（1 个样本）→56%（250 个样本），覆盖率常呈对数线性增长。")]],
        [[N("在所测无自动验证器的设置下，投票与奖励模型约百次后趋于饱和，未充分接近覆盖率上限。")]]]
r_prm = [paper_cell("Let's Verify Step by Step", "Lightman et al., 2023, arXiv", domain="数学（MATH），非 SQL"),
         [[N("结果监督只标注最终对错，无法直接提供步骤级错误信息。")]],
         [[N("① 标注步骤为正、负或中性，发布 PRM800K；② 训练过程奖励模型；③ 测试时将中性并入正类，分数连乘后挑解答。")]],
         dict(tex=r"\mathrm{score}(s)=\prod_{j=1}^{J}p_{\theta}(\mathrm{step}_j\ \mathrm{correct})",
              paras=[[G("本次整理：据论文文字定义写成公式。", size=10.5), N("各步“正类或中性”的预测概率相乘，作为评分；不能直接视为校准后的联合正确概率。")]]),
         [[N("相对结果监督奖励模型：MATH 的 500 题子集上 best-of-1860 解出 78.2%（结果监督 72.4%）。")]],
         [[N("相对投票：需步骤级标注；大规模 PRM/ORM 的训练数据并不完全可比，不能将差值全部归因于监督粒度。")]]]
grid(s, 0.5, 1.12, COLW, HDR, [r_sc, r_mk, r_prm], "auto")
finish(s, "Wang et al. (2023)；Brown et al. (2024)；Lightman et al. (2023)；Chen et al. (2021)。数字均为各论文原文报告",
       """这一页比较“并行采样加挑选”这一类，三篇论文正好对应三个问题。
Self-Consistency 针对贪心解码只保留一条推理路径的局限：采很多条推理路径，按最终答案投票。它的好处是完全不用训练，在 GSM8K 上提升了将近 18 个点；问题是只能选最常见的答案，正确但少见的答案会被投掉。
Large Language Monkeys 研究的是“多试几次到底有多少用”。它用 pass@k 衡量覆盖率，公式里 N 是采样次数，C_i 是答对次数，方括号里就是随机抽 k 个至少一个对的概率。它发现覆盖率在论文测试的采样范围内继续提高，而所测投票和奖励模型约百次后趋于饱和。
Let's Verify 解决的是挑选不准：将步骤标为正、负或中性来训练过程奖励模型；评分时将中性并入正类。在 MATH 的 500 题子集上，best-of-1860 的结果为 78.2%，结果奖励模型为 72.4%，相差 5.8 个百分点；两者的大规模训练数据并不完全可比。公式是我们根据论文的文字定义整理的，不是原文公式。""")

# ---------------------------------------------------------------- 5 refinement + allocation
s = new("通用文献背景 2｜顺序修正与预算分配", "非 SQL 实验")
r_sr = [paper_cell("Self-Refine", "Madaan et al., 2023, arXiv", domain="多类生成 / 代码 / 推理，非 SQL"),
        [[N("一次生成的输出常有可改进之处，而额外训练或标注的成本高。")]],
        [[N("① 模型写初稿；② 同一模型给出反馈；③ 按反馈修改；重复，直到满足停止条件（固定轮数或反馈给出停止信号）。")]],
        dict(tex=r"y_{t+1}=\mathcal{M}(p_{\mathrm{refine}}\,\|\,x\,\|\,y_t\,\|\,fb_t)",
             paras=[[G("流程概括，据论文算法 1。", size=10.5), N("‖：拼接提示；x：输入；fb_t：第 t 轮反馈；同一模型 M 分别生成初稿、反馈和修订稿。")]]),
        [[N("相对一次生成：7 类任务的表现平均绝对提升约 20%（原文汇总口径），并非统一准确率；GPT-4 也有收益。")]],
        [[N("相对有外部反馈的修正：反馈来自模型自己，可能看不出自己的错；调用量随修正轮数增加。")]]]
r_hu = [paper_cell("LLMs Cannot Self-Correct Reasoning Yet", "Huang et al., ICLR 2024", domain="问答推理，非 SQL"),
        [[N("此前“自我修正有效”的结论，是否依赖了标准答案来决定何时停？")]],
        [[N("① 区分用标准答案控制停止（oracle）与完全不用外部信息（内在自我修正）；② 在 GSM8K、CommonSenseQA、HotpotQA 上重测。")]],
        [[G("规则概括（无核心公式）：", size=10.5)], [N("内在自我修正＝回答→自评→重答，全程拿不到“对或错”的信号。oracle 版本在答对时就停，等于使用了标准答案信息。")]],
        [[N("相对此前报告：指出停止规则利用了标准答案；去掉后 GPT-3.5 在 CommonSenseQA 上 75.8→38.1（一轮修正）。")]],
        [[N("只测提示法与问答推理；结论针对内在修正，不能直接推广到有外部反馈的情形；SQL 执行反馈也不等于正确性标签。")]]]
r_sn = [paper_cell("Scaling Test-Time Compute Optimally", "Snell et al., 2024, arXiv", domain="数学（MATH），非 SQL"),
        [[N("推理预算固定时，应该怎样花最有效？能否替代把模型做大？")]],
        [[N("① 先训练 PRM 与修正模型，测试时冻结；② 按题目难度分档选搜索或修正策略；③ 比较 best-of-N，并与参数约为其 14 倍的模型做 FLOPs 对照。")]],
        dict(tex=r"\theta^{*}(q,N)=\arg\max_{\theta}\ \Pr_{y\sim\mathrm{Target}(\theta,N,q)}\left[y=y^{*}(q)\right]",
             paras=[[G("等价改写：作者式 1 中指示函数的期望写成概率。", size=10.5), N("θ：测试时策略的超参数；N：计算预算；q：题目。对每题选准确率最高的策略。")]]),
        [[N("在部分设置下，用约 1/4 的测试时计算达到相近效果；有利的难度与负载条件下，可胜过参数约为其 14 倍的模型。")]],
        [[N("难度分档用每题 2,048 个样本，估计开销未计入主分析；修正模型需预训练外的微调。高推理负载下，难题可能更适合大模型。")]]]
grid(s, 0.5, 1.12, COLW, HDR, [r_sr, r_hu, r_sn], "auto")
finish(s, "Madaan et al. (2023)；Huang et al. (2024)；Snell et al. (2024)。数字均为各论文原文报告",
       """第二组是“顺序修正”和“计算分配”。
Self-Refine 让同一个模型写初稿、生成反馈、再修改，循环到停为止。原文报告，在 7 类任务的各自指标上平均绝对提升约 20%；不能统一解读为准确率提高 20 个百分点。公式这一格是我们根据它的算法 1 做的流程概括，不是作者写的数学式。
但 Huang 等人的工作给了一个重要反证：很多“自我修正有效”的实验，其实用标准答案来决定什么时候停，使用了标准答案信息。去掉这个信号以后，GPT-3.5 在 CommonSenseQA 上从 75.8 掉到 38.1。这些实验说明：在所测问答推理任务中，仅凭模型自身反馈进行修正并不可靠。对我们来说这点很关键，因为 SQL 执行器能提供报错与结果等外部反馈，但这些反馈本身不能保证语义正确。
Snell 等人回答的是“预算怎么花”：按题目难度分档，选择搜索或顺序修正的策略。在部分设置下，约用 best-of-N 四分之一的测试时计算就能达到相近效果。但难度估计使用每题 2,048 个样本，这部分开销没有计入主分析；PRM 和修正模型也需要事先训练。与大约 14 倍参数模型的比较还取决于题目难度和预训练、推理负载，因此不能直接讲成端到端省四倍算力。""")

# ---------------------------------------------------------------- 6 tree search
s = new("从通用推理到 SQL｜rStar 与 Alpha-SQL", "通用→SQL")
r_rs = [paper_cell("rStar", "Qi et al., 2024, arXiv", domain="数学 / 常识，非 SQL"),
        [[N("小模型推理弱、自评不可靠；不想微调，也不想借助更强的模型。")]],
        [[N("① MCTS 在 5 种推理动作上搜索；② Phi3-mini-4k（3.8B）补全部分轨迹，检验末端答案是否一致；③ 保留一致轨迹，按奖励×末端置信度选择。")]],
        dict(tex=r"\mathrm{UCT}(v,a)=\frac{Q(v,a)}{N(v,a)}+c\sqrt{\frac{\ln N(v)}{N(v,a)}}",
             paras=[[G("标准 UCT，按统一父节点—动作记号表示。", size=10.5), N("前项：平均回报（利用）；后项：试得少的动作加分（探索）；c 权衡两者。")]]),
        [[N("相对少样本 CoT：32 次 MCTS rollout 让 LLaMA2-7B 在 GSM8K 上 12.51%→63.91%，无需微调。")]],
        [[N("相对单次生成：32 次 rollout 另加判别；GSM8K 上 LLaMA2-7B 平均约 166 次调用（附录 A.2）；未用于后续训练"), AN, N("。")]]]
r_al = [paper_cell("Alpha-SQL", "Li et al., ICML 2025", "alpha", domain="Text-to-SQL"),
        [[N("零样本（不用任务数据微调）时，模型难把通用知识迁移到复杂 schema 和 SQL；微调又贵，换模型还得重做。")]],
        [[N("① 把写 SQL 拆成 7 种动作（改写问题、选表列、识别取值、识别函数、生成、修正、结束）；② 大模型执行每个动作；③ 24 次 rollout，用自洽奖励回传；④ 最后选执行结果最一致的 SQL。")]],
        dict(tex=r"R(y)=\frac{1}{N}\sum_{i=1}^{N}\mathbb{1}\left[\mathrm{Exec}(y)=\mathrm{Exec}(y_i)\right]",
             paras=[[G("等价改写：省略问题 q 与数据库 D 参数。", size=10.5), N("对路径末端的 SQL y 再采 N=5 个 SQL，执行结果与 y 相同的比例即奖励，不需要标准答案。")]]),
        [[N("相对直接提示同一模型：Qwen2.5-Coder-7B 在 147 题子集上 47.6→64.6；BIRD dev 66.8（7B）、69.7（32B），其中 32B 高于基于 GPT-4o 的 RSL-SQL（67.2），7B 略低。")]],
        [[N("相对单次生成：每题 24 次 rollout、每次扩展采 3 次、奖励再采 5 次，推理成本未报告；消融只在 147 题上，差异 0.4–1.8 点。")]]]
links, yy = grid(s, 0.5, 1.12, COLW, HDR, [r_rs, r_al], "auto")
LINKS.append((links[1], "alpha"))
strip_check(yy, 1.0)
rect(s, 0.5, yy + 0.16, 12.33, 1.0, fill="FBE9DF", rounded=True)
text(s, 0.65, yy + 0.2, 12.0, 0.95, [
    [B("比较结论："), N("rStar 用推理动作与轨迹一致性做搜索；Alpha-SQL 把动作落到 SQL 生成与修正，并用执行结果一致性给奖励。")],
    [N("需要继续验证：搜索是否比同预算多采样更划算？执行结果一致是否真的能选中正确 SQL？演算见附录 B。")],
], size=12, space_after=2)
finish(s, "Qi et al. (2024)；Li et al. (2025)。Alpha-SQL 的 147 题子集（SDS）沿用 CHESS 的划分",
       """第三组是树搜索。通用方法里我选了 rStar：它用蒙特卡洛树搜索在几种“类人推理动作”上展开，再用另一个能力相近的小模型补全部分轨迹做判别，保留最终答案一致的轨迹，再按论文的奖励与末端置信度评分选择。选路径用的是标准 UCT 公式：前一项是平均回报，鼓励利用；后一项给试得少的动作加分，鼓励探索。
Alpha-SQL 把这个思路搬到 Text-to-SQL：把写 SQL 拆成 7 种动作，比如改写问题、选表和列、识别取值、生成 SQL、根据执行结果修正。它最重要的设计是奖励：不需要标准答案，而是再采 5 个 SQL，看执行结果和当前 SQL 一致的比例。这背后的假设是“答对的答案更容易被反复得到”。
效果上，7B 模型在 BIRD 开发集上的 EX 为 66.8%，略低于 RSL-SQL 的 67.2%；超过这一基线的是 32B 版本，EX 为 69.7%。缺点是推理成本没有报告，每题包含多次搜索扩展与奖励采样，具体调用总量未报告；而且消融实验只在 147 题上做，差异不到 2 个点。
下面是一个教学示例，说明自洽奖励怎么算，以及 UCT 为什么会先去试回报低但很少试过的动作。""")

# ---------------------------------------------------------------- 7 CSC vs R3
s = new("文献比较 4｜合并修正与组级排序", "Text-to-SQL")
r_csc = [paper_cell("CSC-SQL", "Sheng & Xu, 2025, arXiv", "csc"),
         [[N("自洽投票的多数答案不一定对，且它与 pass@k 的差距随样本数扩大；常见的自我修正多只修语法错误。")]],
         [[N("① 采 n 个 SQL（T=0.8），按执行结果分组；② 结果全一致时直接输出；否则取前两组的代表 SQL；③ 将两条 SQL 和执行结果交给合并修正模型，再采 8 个并投票；④ 用 GRPO 训练修正器及部分生成模型。")]],
         dict(tex=r"R=R_{\mathrm{EX}}+0.1\cdot R_{\mathrm{Format}}",
              paras=[[G("作者原式（GRPO 训练奖励）。", size=10.5), N("R_EX：执行结果与标准一致记 1；R_Format：按 <think><answer> 格式输出记 1。")]]),
         [[N("相对同生成模型、同初始样本数的投票：BIRD dev 提升 0.72–5.54 点；7B（GRPO，n=64）66.15→69.19；BIRD 私有测试 71.72（7B）、73.67（32B）。")]],
         [[N("相对自洽投票：多一步修正，计算更多；样本缺乏多样性时收益小；同一 7B 模型的 SC 结果中，GRPO 收益随 n 增大而缩小（8：+2.77；64：+1.70 点）。")]]]
r_r3 = [paper_cell("R³-SQL", "Han et al., Findings of ACL 2026", "r3"),
        [[N("① 执行结果相同的 SQL 被打不同分（功能等价候选的评分不一致）；② 候选池里没有对的 SQL 时，排序无法补救（召回有上限）。")]],
        [[N("① 32B 模型生成并执行 32 个候选；② 代理判断需重采时，再采 1,024 个、保留前 32；③ 按执行结果分组，组间比较得 r_list；④ 用组大小×组内最佳倒数排名得 r_point，打破平局；前两组再比较。")]],
        dict(tex=r"r_{\mathrm{point}}(g)=|g|\cdot\max_{s\in g}\mathrm{RR}_s",
             paras=[[G("作者原式（式 4）。", size=10.5), N("|g|：组大小（一致程度）；RR_s：点式排序器给出的倒数排名。组按 (r_list, r_point) 排序：先比两两胜场，平局再比它。")]]),
        [[N("相对统一生成设置及适用排序器下的 CSC/CHASE/XiYan 选择基线：BIRD dev 75.03（CHASE 73.34）；5 个基准平均 70.65；重采样让候选召回 78.80→82.72。")]],
        [[N("表 8 报选择耗时 1.56 秒/题（8×H200），未清楚拆分生成与重采样计时；点式排序器在 BIRD 上训练，领域外略拖后腿；评测剔除了标准答案为空的题。")]]]
links, yy = grid(s, 0.5, 1.12, COLW, HDR, [r_csc, r_r3], "auto")
LINKS += [(links[0], "csc"), (links[1], "r3")]
strip_check(yy, 0.95)
rect(s, 0.5, yy + 0.16, 12.33, 0.95, fill="FBE9DF", rounded=True)
text(s, 0.65, yy + 0.2, 12.0, 0.9, [
    [B("比较结论："), N("CSC-SQL 用前两组生成修正答案，可改变候选池；R³-SQL 对等价候选分组排序，必要时重采样补充候选。")],
    [N("需要继续验证：收益来自候选更好，还是选择更准？生成、重采样和选择的成本应分别报告。排序演算见附录 B。")],
], size=12, space_after=2)
finish(s, "Sheng & Xu (2025)；Han et al. (2026)。两篇的数字来自不同生成模型与评测子集，不能直接排名",
       """这一页是 Text-to-SQL 里专门改进“挑选”的两篇。
CSC-SQL 的观察是：投票选出的第一名不一定对，但正确答案经常在票数前两名里。所以它把前两组的 SQL 和执行结果一起交给一个“合并修正”模型，再采 8 个、再投票。修正器及部分生成模型使用 GRPO 训练，奖励就是执行正确记 1、格式正确加 0.1。相对同条件的自洽投票，原文报告它提升 0.72–5.54 个百分点。值得注意的是，GRPO 训练带来的提升随样本数增加而缩小，这提示两者可能有部分替代关系，但该实验尚不足以确认其机制。
R³-SQL 解决两个问题：执行结果相同的 SQL 被打不同的分；以及候选池里根本没有对的答案。它先由代理判断是否需要替换候选池，必要时重采样；再按执行结果分组并排序，用 r_list 比较组间偏好，平局时比较“组大小乘组内最佳倒数排名”。最后比较排序前两组，选出最终 SQL。具体排序演算移到附录 B；正文重点比较改变候选池与改进选择这两个作用。
请注意两篇的数字不能直接比：R³-SQL 用 32B 生成模型，而且评测剔除了标准答案为空的题；它报告的 1.56 秒也只是挑选阶段的时间。""")

# ---------------------------------------------------------------- 8 multi-turn vs single
s = new("单轮任务与多轮交互：区分任务协议和求解流程", "多轮")
text(s, 0.5, 1.1, 12.33, 0.75, [
    [B("任务协议：", color=ORANGE), N("用户单轮提问或多轮对话；"), B("求解流程：", color=BLUE),
     N("模型可多步执行、读取结果并修正。两者可以组合，单轮任务也可采用多步求解。")]], size=14)
mt_rows = [
    ("输入", "完整问题＋schema", "问题逐步给出，可能含糊或缺信息", "完整问题＋schema"),
    ("状态", "无跨轮用户历史；可有内部执行状态", "对话历史；数据库可能被增删改", "执行历史（报错、结果）"),
    ("反馈来源", "最终评分；可使用执行反馈", "（模拟）用户的澄清与评价", "执行结果与报错"),
    ("模型动作", "可多步求解，最终提交 SQL", "提问、执行、提交", "执行、修改、提交"),
    ("评测", "EX（执行结果一致）", "最终数据库状态、测试用例、Pass^k", "EX（最终 SQL）"),
    ("主要难点", "理解 schema、写对复杂查询", "何时该问、记住历史、处理写操作", "读懂报错，避免空转"),
    ("代表", "BIRD、Spider", "SParC、CoSQL、DySQL-Bench、BIRD-INTERACT", "Alpha-SQL 的修正动作；ReAct 式智能体"),
]
grid(s, 0.5, 1.95, [1.6, 3.2, 4.1, 3.43], ["维度", "单轮用户输入", "多轮用户对话", "多步工具交互"],
     [[[[B(a)]], [[N(b)]], [[N(c, color=NAVY)]], [[N(d)]]] for a, b, c, d in mt_rows], 0.62, size=12.5, hsize=12.5)
finish(s, "本次整理；参照 DySQL-Bench 图 1 对单轮单步、单轮多步、多轮多步的区分（Sun et al., 2025）以及 SParC、CoSQL（Yu 等，2019）",
       """这一页回答“多轮 Text-to-SQL 和普通 Text-to-SQL 有什么区别”。需要区分用户对话轮次与求解过程的工具调用次数；单轮任务也可以通过多步执行与修正来完成。
单轮描述的是用户只给出一个问题，并不限制求解器只能调用一次模型。求解过程中仍可执行 SQL、读取报错并修正；最终按基准协议评分。
这里区分两类交互。一种是与用户多轮：用户的问题一步步给出，可能含糊，模型需要决定什么时候去问；有的基准还包括增删改操作，所以数据库本身的状态会变化，评测就要看最终数据库状态。另一种是求解过程中与数据库多步交互：问题是完整的，但模型可以执行 SQL、看报错和结果，再修改。Alpha-SQL 的修正动作、以及我们自训练流程里的执行—修复循环，都属于这一种。
这张表按任务协议与求解流程对照整理，三列不是互斥类别；单轮和多轮用户任务都可以采用多步工具交互。""")

# ---------------------------------------------------------------- 9 original evidence of two-sided interaction
s = new("内层任务｜用用户澄清与数据库反馈完成 SQL 任务", "交互环境")
from PIL import Image
fig = PAPER_FIGURES["birdint"] if "PAPER_FIGURES" in globals() else json.load(open(os.path.join(os.path.dirname(__file__), "paper_figures/manifest.json")))["birdint"]
path = os.path.join(os.path.dirname(__file__), "paper_figures", fig["image"])
with Image.open(path) as im:
    iw, ih = im.size
fw = 7.7
fh = fw * ih / iw
s.shapes.add_picture(path, Inches(0.5), Inches(1.85), Inches(fw), Inches(fh))
lib.rec(s, "img", path, 0.5, 1.85, fw, fh)
text(s, 0.5, 1.17, 7.7, 0.48, [[B("BIRD-INTERACT 原文 Fig.1（PDF 第 2 页）")]], size=16)
text(s, 0.5, 5.32, 7.7, 0.63, [[N("图中原例：围绕 urgent care 的歧义澄清，随后执行、修复，并处理依赖前一步的追问。")]], size=12.5)
text(s, 8.55, 1.16, 4.28, 0.42, [[B("可以在原文定位的机制")]], size=16)
text(s, 8.55, 1.9, 4.28, 3.85, [
    [B("BIRD §3.2–3.3："), N("注入歧义；两阶段用户模拟器回答澄清请求。")],
    [B("BIRD §4.2："), N("a-Interact 自主选择用户、知识与数据库工具；动作消耗预算。")],
    [B("DySQL §V、Fig.5："), N("用户—agent—数据库三方交互，用户可按前一步输出继续回应。")],
    [G("两篇为交互环境与评测依据，不是我们的训练方法。", size=11.5)],
], size=13, space_after=12)
rect(s, 0.5, 6.13, 12.33, 0.72, fill="FBE9DF", rounded=True)
text(s, 0.7, 6.21, 11.93, 0.53, [[B("本项目范围："), N("内层完成一次任务；外层用交互轨迹更新模型，并让新模型继续生成下一轮轨迹。")]], size=13, space_after=0)
source = "原图：arXiv:2510.05318v3 Fig.1；协议：§3.2–4.2。DySQL：arXiv:2510.26495v2 §V、Fig.5"
finish(s, source, "用户澄清、状态追问与数据库工具均有原文依据。当前图为BIRD原文Fig.1；自编订单对话已删除。两篇提供环境和评测，不能当成新训练方法。")

# ---------------------------------------------------------------- 10 source roles and restored project objective
s = new("研究依据｜交互机制已有，重点检验跨轮长期效用", "RSI 定位")
rows = [
    ("BIRD-INTERACT", "用户澄清、数据库工具、任务测试与预算", "定义每一轮交互任务与评测环境"),
    ("MTSQL-R1", "交互轨迹选择与迭代自训练；历史约束验证", "最接近的训练机制，不能将迭代自训练本身当作新意"),
    ("SQLConductor", "工作流稳定性筛选、搜索转策略与逐步决策", "作为选择和策略学习参考，仍须对照不同任务协议"),
    ("RAISE / SERL-SQL", "主动数据库探索 / 执行反馈局部学习信号", "帮助定义交互轨迹，不直接证明跨轮长期效用"),
    ("本项目 Phase 3", "同一起点、不同首批轨迹；继续生成—训练—评估", "检验首轮效用排序能否预测后续递归改进的效用"),
]
grid(s, 0.5, 1.12, [2.2, 5.0, 5.13], ["依据", "已有机制或设计", "在本研究中的作用"],
     [[[[B(a)]], [[N(b)]], [[N(c)]]] for a,b,c in rows], 0.82, size=12, hsize=12.5)
rect(s, 0.5, 5.93, 12.33, 0.9, fill="FBE9DF", rounded=True)
text(s, 0.7, 6.02, 11.93, 0.67, [[B("核心问题："), N("对当前一次更新最有用的交互轨迹，是否也最有利于后续多轮递归自训练？")]], size=16, space_after=0)
finish(s, "论文机制见原文细读；项目依据：README Phase 3、scripts/phase3.py、scripts/analyze_phase3.py。尚不构成新颖性或效果结论",
       "交互环境与算法机制是基础；恢复项目原有即时效用与长期效用问题。比较的对象是轨迹批次或选择规则，而不是跨论文排行榜。")

# ---------------------------------------------------------------- 11 two loops, explicitly showing recursive feedback
s = new("我们的 idea｜内层交互求解，外层递归自训练", "RSI 闭环")
rect(s, 0.5, 1.13, 12.33, 1.57, fill=CARD, rounded=True)
text(s, 0.7, 1.27, 11.93, 0.42, [[B("内层：当前智能体 A_t 完成一次任务（参数不变）")]], size=17, space_after=0)
text(s, 0.7, 1.95, 11.93, 0.49, [[N("用户澄清 → 数据库探索 / 执行 → 读取反馈 → 修复 / 提交，记录完整交互轨迹。")]], size=15, space_after=0)
rect(s, 0.5, 3.02, 12.33, 2.86, fill="FBE9DF", rounded=True)
text(s, 0.7, 3.16, 11.93, 0.42, [[B("外层：用轨迹更新智能体，再由新智能体生成下一轮数据")]], size=17, space_after=0)
flow = [("1  A_t 交互生成", "训练任务上的完整轨迹 D_t"), ("2  核验与选择", "从 D_t 中选训练批次 B_t"),
        ("3  更新参数", "继续训练 A_t → A_{t+1}"), ("4  回到下一轮", "A_{t+1} 重新交互与采集")]
for i, (head, caption) in enumerate(flow):
    x = 0.7 + i * 3.03
    rect(s, x, 3.87, 2.82, 1.14, fill=WHITE, rounded=True)
    text(s, x + 0.07, 3.99, 2.68, 0.34, [[B(head)]], size=13.5, space_after=0)
    text(s, x + 0.07, 4.48, 2.68, 0.43, [[N(caption)]], size=11.5, space_after=0)
    if i < 3:
        arrow(s, x + 2.86, 4.3, 0.13, 0.22)
text(s, 0.7, 5.26, 11.93, 0.42, [[B("递归的关键："), N("更新后的模型会改变后续生成的数据，下一轮继续用这些新数据改进。")]], size=14, space_after=0)
text(s, 0.5, 6.17, 12.33, 0.65, [[G("本研究将 RSI 操作化为多轮自生成数据的参数更新；不据此声称改进器、选择规则或训练算法本身已学会自我改写。", size=12)]], size=12)
finish(s, "闭环依据：scripts/phase3.py 的 gen → train → eval；init_adapter 延续上一轮模型。双向用户交互仍待接入",
       "单任务内的交互次数、外层训练轮数必须分开。现有脚本已有只读SQL的外层递归自训练，不表示双向交互环境已实现，也不表示元改进能力增强。")

# ---------------------------------------------------------------- 12 explicit immediate and long-horizon utility
s = new("核心问题｜即时有效的轨迹，也有长期效用吗？", "轨迹效用")
text(s, 0.5, 1.13, 12.33, 0.77, [[N("从同一个 A_0 出发，用不同首批轨迹 B 形成分支；之后各分支采用相同后续规则，继续生成新数据并训练到 H 轮。")]], size=15)
rect(s, 0.5, 2.13, 6.02, 2.6, fill=CARD, rounded=True)
rect(s, 6.8, 2.13, 6.03, 2.6, fill=CARD, rounded=True)
text(s, 0.7, 2.27, 5.62, 0.45, [[B("即时效用：第一次更新带来多少提升")]], size=16)
add_formula(s, r"U^{1}(B)=P(A_{1}^{B})-P(A_{0})", 0.75, 3.0, 5.4, 0.55)
text(s, 0.7, 3.84, 5.62, 0.64, [[N("衡量首批数据 B 对第一轮训练的帮助；不能直接说明后续还能改善多少。")]], size=13)
text(s, 7.0, 2.27, 5.63, 0.45, [[B("长期效用：沿分支继续改进后的收益")]], size=16)
add_formula(s, r"U^{H}(B)=\sum_{h=1}^{H}\gamma^{h-1}[P(A_h^B)-P(A_{h-1}^B)]", 7.05, 3.0, 5.4, 0.6)
text(s, 7.0, 3.84, 5.63, 0.64, [[N("现有配置 γ=1，等于末轮相对起点的提升；不是把各轮性能相加。")]], size=13)
text(s, 0.5, 5.02, 12.33, 0.57, [[B("要检验："), N("按 U¹ 排名好的批次，到 Uᴴ 还好吗？排序变化是否超出测量噪声？")]], size=16)
text(s, 0.5, 5.78, 12.33, 0.97, [
    [N("P：独立验证性能。现有脚本使用 sampled pass rate；迁移到双向任务后需预先定义完整任务成功率等口径。")],
    [G("学习曲线、后续增益、覆盖率、重复成功率与总成本另行报告。长期排名反转目前是待验证问题，不是已有结论。", size=11.5)],
], size=12.5, space_after=7)
finish(s, "效用定义：scripts/analyze_phase3.py；当前 configs/phase3.yaml：H=2、γ=1。不将 sampled pass rate 与 pass@k 或 Pass^k 混用",
       "比较首批轨迹的即时与长期效用时，后续选择规则固定；不同首批模型会产生不同后续数据。γ=1时折扣增益和化为最终性能减起点性能。")

# ---------------------------------------------------------------- 13 tests that identify recursive versus one-off improvement
s = new("验证方案｜检验递归收益、长期排序与计算成本", "RSI 实验")
rows = [
    ("E0 环境接入", "保留用户澄清＋数据库反馈；独立训练、验证与测试任务", "固定用户协议、工具权限和动作预算", "完整任务 SR；协议一致性"),
    ("E1 首批长期效用", "同 A_0、不同首批 B；之后统一规则，训练到 H 轮", "首批候选随机带入；独立重复测量作噪声基线", "U¹ / Uᴴ 排序；后续增益与区间"),
    ("E2 逐轮选择规则", "从同 A_0 比较随机、稳定性、难度/多样性等逐轮策略", "首轮共池；之后各模型产生新数据；控制训练量", "逐轮成功率、覆盖与可靠性"),
    ("E3 递归与成本", "新模型采新数据 vs 固定数据重训 / 每轮重启 / 一次更新", "控制或分项报告全部采样、训练与部署计算", "同成本的末轮质量；负迁移与回退"),
]
grid(s, 0.5, 1.12, [1.65, 4.55, 3.9, 2.23], ["实验", "要回答的问题 / 设计", "关键控制", "观察量"],
     [[[[B(a)]], [[N(b)]], [[N(c)]], [[N(d)]]] for a,b,c,d in rows], 1.13, size=11.5, hsize=12)
text(s, 0.5, 6.25, 12.33, 0.65, [[G("现有 Phase 3 配置 H=2、后续规则固定；双向环境迁移和更长 H 均待验证。末轮测试不参与选择，不预设多轮一定更好。", size=11.5)]], size=11.5)
finish(s, "项目设计：README Phase 3、phase3.py、analyze_phase3.py；交互依据：BIRD、MTSQL-R1、SQLConductor。仅修订材料，未运行新实验",
       "E1隔离首批轨迹的长期效用，E2比较完整选择策略，两者不能混为一个实验。多轮数据回流可能有收益，也可能退化；须对照噪声与计算成本。")

MAIN_COUNT = len(SLIDES)

# ================================================================ Appendix directory
s = new("附录导航｜方法流程、实验证据与公式分开查阅", "附录")
APPX_DIV = s
text(s, 0.5, 1.12, 12.33, 0.65, [[N("正文按问题比较；附录按论文展开。点击目录中的页码可跳转，逐篇页可返回正文对应表格。")]], size=14)
# The rows and page numbers are filled after all targets have been created.
finish(s, None, "附录按查阅任务组织：A 区每篇先看方法流程，再看实验证据；B 区集中看公式、符号、假设和演算；最后是参考文献。逐篇首页使用论文原文主图，标注 arXiv 版本、图号与 PDF 页码，配中文读图说明。目录和逐篇页提供往返跳转。")

FIGURE_DIR = os.path.join(os.path.dirname(__file__), "paper_figures")
PAPER_FIGURES = json.load(open(os.path.join(FIGURE_DIR, "manifest.json")))
READING_GUIDE = {
    "alpha": "从左到右：问题与数据库 → 搜索动作 → 选择、扩展、模拟、回传 → 按执行结果选 SQL。下方显示 UCT 与自洽奖励。",
    "csc": "从左到右：并行生成与执行分组 → 取前两组构造合并修正提示 → 再次生成与投票。下方为 GRPO 训练。",
    "r3": "从左到右：候选池 → 按执行结果分组 → 组间偏好与组内最佳候选两路评分 → 输出选中组。重采样模块见文字与公式页。",
    "dysql": "先看上半部：数据库记录转树，再生成初始任务；下半部通过验证委员会和筛选得到精炼任务。动态交互评测见下一页。",
    "birdint": "先看左侧任务、数据库和模拟用户；右侧依次展示澄清、SQL 执行与修复、以及依赖前一状态的追问。",
}


def nav_button(slide, label, target, x=9.5, y=6.61, w=3.3):
    shape = text(slide, x, y, w, 0.32, [[O(label)]], size=10.5,
                 align="r", space_after=0, name="Navigation")
    NAV.append((shape, target))
    return shape


def stack(slide, x, y, w, blocks, bottom=6.95):
    """Place (heading, paras, size) blocks top-down using estimated heights."""
    for head, paras, size in blocks:
        if head:
            text(slide, x, y, w, 0.4, [[B(head)]], size=13, space_after=0)
            y += 0.38
        h = lib.est_height(paras, w - 0.08, size, 1.12, 3) + 0.1
        text(slide, x, y, w, h, paras, size=size, space_after=3)
        y += h + 0.08
    if y > bottom + 0.02:
        lib.WARN.append(f"STACK OVERFLOW y={y:.2f} :: {blocks[0][0]}")
    return y


def detail_pages(key, code, short, info, problem, contrib, steps, tex_list, symbols, assumptions,
                 exp_rows, results, pros, cons, future, src, note_a, note_b):
    # Page 1 follows the reference deck: original method diagram plus Chinese interpretation.
    s1 = new(f"{code}　{short}｜原文主图与方法要点", "附录 A")
    APPX[key] = s1
    fig = PAPER_FIGURES[key]
    image_path = os.path.join(FIGURE_DIR, fig["image"])
    from PIL import Image
    with Image.open(image_path) as image:
        iw, ih = image.size
    scale = min(7.98 / iw, 4.38 / ih)
    fw, fh = iw * scale, ih * scale
    fx, fy = 0.5 + (7.98 - fw) / 2, 1.28 + (4.38 - fh) / 2
    s1.shapes.add_picture(image_path, Inches(fx), Inches(fy), Inches(fw), Inches(fh))
    lib.rec(s1, "img", image_path, fx, fy, fw, fh)
    text(s1, 0.5, 1.06, 7.98, 0.3, [[G(f"原文 Fig. {fig['figure']} · PDF 第 {fig['pdf_page']} 页")]], size=10.5, space_after=0)
    text(s1, 0.5, 5.83, 7.98, 0.68, [[B("读图顺序："), N(READING_GUIDE[key])]], size=12, space_after=0)
    stack(s1, 8.8, 1.1, 4.03, [
        ("研究问题", [[N(problem)]], 11.5),
        ("主要贡献", [bl(N(c)) for c in contrib], 11.5),
        ("使用前提与理解边界", [[N(assumptions)]], 11),
    ], bottom=6.5)
    # Preserve complete bibliographic metadata in notes and the reference list.
    info_text = "\n".join("".join(t for t, _ in row) for row in info)
    figure_source = f"原文图：arXiv:{fig['arxiv']}，Fig. {fig['figure']}，PDF 第 {fig['pdf_page']} 页。"
    finish(s1, figure_source, note_a + "\n" + figure_source + "\n读图顺序：" + READING_GUIDE[key] +
           "\n" + info_text + "\n本页使用论文原图裁切，未重绘；完整步骤、公式与符号另见附录 B。")
    # page 2
    s2 = new(f"{code}　{short}｜实验证据、优势与局限", "附录 A")
    RX, RW = 6.8, 6.03
    exp_size = 10.5 if key == "birdint" else 11
    firsts, yy = grid(s2, 0.5, 1.1, [1.3, 4.7], ["实验要素", "设置"],
                      [[[[B(a)]], [[N(b)]]] for a, b in exp_rows], "auto", size=exp_size, hsize=12)
    stack(s2, 0.5, yy + 0.1, 6.0, [("作者讨论的未来方向", [[N(future)]], exp_size)])
    stack(s2, RX, 1.08, RW, [("具体结果（论文报告）", [bl(N(r)) for r in results], 11.5),
                                ("相对已有方法的优点", [bl(N(r)) for r in pros], 11.5),
                                ("局限，以及结果尚不能证明什么", [bl(*([N(r)] if isinstance(r, str) else r)) for r in cons], 11.5)])
    finish(s2, src, note_b)
    DETAILS.append(dict(key=key, code=code, short=short, steps=steps, formulas=tex_list,
                        symbols=symbols, assumptions=assumptions, src=src,
                        method=s1, evidence=s2))
    for page in (s1, s2):
        nav_button(page, "返回正文比较表", SLIDES[MAIN_ORIGIN[key] - 1][0])
        nav_button(page, "附录目录", APPX_DIV, x=0.5, w=1.4)
    nav_button(s1, "下一页：实验证据", s2, x=6.9, w=2.3)
    nav_button(s2, "原文主图", s1, x=6.9, w=2.3)



PROTECT = {"Monte", "Carlo", "Bradley", "Terry"}


def sentence_case(title):
    out, start = [], True
    for word in title.split(" "):
        parts = word.split("-")
        new = []
        for j, p in enumerate(parts):
            core = p.strip("()?:,.'")
            keep = (not core or any(c.isupper() for c in core[1:]) or (core.isupper() and len(core) > 1) or core in PROTECT
                    or any(c.isdigit() for c in core) or (start and j == 0))
            new.append(p if keep else p.lower())
        out.append("-".join(new))
        start = word.endswith(":") or word.endswith("?")
    return " ".join(out)


def apa(key, venue=None, title_override=None, year=None):
    m = META[key]
    names = []
    for a in m["authors"]:
        last, _, first = a.partition(", ")
        ini = []
        for part in first.replace(".", " ").split():
            if part.islower():
                ini.append(part)
                continue
            sub = part.split("-")
            ini.append("-".join(x[0] + "." for x in sub if x))
        names.append(f"{last}, {' '.join(ini)}")
    if len(names) == 1:
        au = names[0]
    elif len(names) <= 20:
        au = ", ".join(names[:-1]) + ", & " + names[-1]
    else:
        au = ", ".join(names[:19]) + ", ... " + names[-1]
    year = year or m["date"][:4]
    raw = (title_override or m["title"]).replace("$\\tau$", "τ").replace("$^3$", "³")
    title = sentence_case(raw)
    if venue:
        return f"{au} ({year}). {title}. {venue}. https://arxiv.org/abs/{key}"
    return f"{au} ({year}). {title} (arXiv:{key}). arXiv. https://doi.org/10.48550/arXiv.{key}"


def info_rows(title, authors, year, venue, key, extra=None, apa_venue=None):
    rows = [[B("题目　"), N(title)], [B("作者　"), N(authors)], [B("年份 / 发表　"), N(f"{year}；{venue}")],
            [B("链接　"), ("arxiv.org/abs/" + key, dict(color=BLUE, url="https://arxiv.org/abs/" + key))]]
    if extra:
        rows.append([B("代码　" if extra.startswith("github.com/") else "项目　"), N(extra)])
    rows.append([B("引用　"), G(apa(key, apa_venue), size=10)])
    return rows


detail_pages(
    "alpha", "A1", "Alpha-SQL",
    info_rows("Alpha-SQL: Zero-Shot Text-to-SQL using Monte Carlo Tree Search",
              "Boyan Li, Jiayi Zhang, Ju Fan, Yanwei Xu, Chong Chen, Nan Tang, Yuyu Luo（港科大（广州）、人民大学、华为）",
              "2025", "ICML 2025（PMLR 267）", "2502.17248", "github.com/HKUSTDial/Alpha-SQL",
              "In Proceedings of the 42nd International Conference on Machine Learning (PMLR 267)"),
    "零样本（不用任务数据微调）时，模型难以把通用知识迁移到复杂 schema 与复杂 SQL；而微调需要标注数据和算力，新模型出现后还要重做。",
    ["把 Text-to-SQL 表述为推理状态树上的搜索", "LLM-as-Action-Model：每一步由大模型生成思维链并执行动作",
     "无需标注的自洽奖励；即插即用，7B–32B 开源模型无需微调"],
    ["根节点＝问题＋schema＋相关取值；MinHash/LSH 召回后，用编辑相似度与 text-embedding-3-large 语义相似度筛选。",
     "选择：用 UCT；未访问过的子节点优先。",
     "扩展：按动作顺序表取合法动作，每个动作采 3 次（T=0.8），结果相同的子节点去重。",
     "模拟：持续扩展到结束节点；每种动作节点在单条路径中最多出现一次；修正动作内部最多迭代 10 轮。",
     "回传：对产出最终 SQL 的动作再采 5 个 SQL（T=1.0）计算自洽奖励，沿路径更新 Q 与 N。",
     "24 次 rollout 后，执行全部候选，选执行结果最一致的 SQL。"],
    [(r"\mathrm{UCT}(v,a)=\frac{Q(v,a)}{N(v,a)}+c\sqrt{\frac{\ln N(v)}{N(v,a)}}", "UCT 教学写法，统一记号"),
     (r"R(y,q,D)=\frac{1}{N}\sum_{i=1}^{N}\mathbb{1}\left[\mathrm{Exec}(y,D)=\mathrm{Exec}(y_i,D)\right]", "作者原式")],
    "符号：N(v,a) 为从节点 v 选动作 a 的次数，N(v) 为节点访问次数，Q 为累积回报，Q/N 为平均回报；y_i 为再采样的 SQL，Exec 为执行结果。",
    "答对的 SQL 更容易被多次采样一致地得到（自洽）；不同路径可能产生当前数据库上执行结果相同的 SQL；一致不保证正确。",
    [("任务与划分", "BIRD dev（1,534 题）、Spider dev（1,034 题）；分析实验用 SDS：BIRD dev 每库取 10%，共 147 题（81/54/12）"),
     ("模型", "Qwen2.5-Coder 7B/14B/32B；对比实验另用 Phi-4"),
     ("预算", "24 次 rollout；扩展 3 次、T=0.8；奖励再采 5 次、T=1.0；修正 ≤10 轮；8×80GB GPU"),
     ("对照方法", "含任务训练组件：SFT CodeS、CHESS、CHASE-SQL、XiYan-SQL；零样本类：DAIL-SQL、SuperSQL、MCS-SQL、RSL-SQL；直接提示 GPT-4o、DeepSeek-R1 等"),
     ("指标", "执行准确率 EX；分析中另报候选上限准确率")],
    ["BIRD dev：66.8（7B）、68.7（14B）、69.7（32B）；零样本 RSL-SQL（GPT-4o）为 67.2；含任务训练组件的 CHASE-SQL 73.0、XiYan-SQL 73.3",
     "Spider dev：14B 达 87.0",
     "SDS 上直接提示 vs 加 Alpha-SQL：Qwen2.5-Coder-7B 47.6→64.6；Phi-4 43.5→60.0",
     "消融：去掉 SQL 修正 −1.8，去掉 schema 选择 −1.5，其余 −0.4 至 −0.7",
     "rollout 从 4 增到 24，上限准确率与最终准确率都上升"],
    ["搜索与奖励无需任务微调；值检索另用 text-embedding-3-large，成本应计入系统评估", "7B 达到与 RSL-SQL（GPT-4o）接近的水平；32B 超过该基线"],
    ["推理成本（调用次数、时间、费用）未报告", "消融只在 147 题上，差异 0.4–1.8 点，未报告方差",
     "与其他系统的底座和组件训练条件不同，不能把系统差异归因于单一机制",
     [N("尚不能证明：在相同计算量下优于“多采样＋投票”（论文未做同计算对照）"), AN]],
    "论文未报告。结论部分只总结了方法与结果。",
    "Li et al. (2025)，正文与表 1–5",
    """Alpha-SQL 的详解第一页。它要解决的是：不微调的情况下，怎么让通用大模型写好复杂 SQL。做法是把写 SQL 变成树搜索：每个节点是一个推理状态，每条边是一个动作，比如选 schema、识别取值、生成 SQL、根据执行结果修正。选择用 UCT，奖励用自洽：再采 5 个 SQL，看执行结果一致的比例。它的核心假设是：答对的 SQL 更容易被多次采样一致地得到。值检索还使用 text-embedding-3-large，因此推理底座开源不等于整套流程完全本地化。""",
    """第二页是实验。主实验在 BIRD 和 Spider 的开发集，分析实验在 147 题的子集上。7B 的 EX 为 66.8%，32B 为 69.7%；其中 32B 在论文所列零样本系统中表现最好，但仍低于含任务训练组件的 CHASE-SQL 和 XiYan-SQL。我们特别关注的局限是推理成本没有报告，以及消融只在 147 题上做、差异很小。另外它没有和“同样计算量的多采样投票”比，所以还不能证明搜索本身比简单多采样更划算。论文没有写未来方向。""")

detail_pages(
    "csc", "A2", "CSC-SQL",
    info_rows("CSC-SQL: Corrective Self-Consistency in Text-to-SQL via Reinforcement Learning",
              "Lei Sheng（武汉理工大学）、Shuai-Shuai Xu（中国科学技术大学）",
              "2025", "arXiv 预印本（arXiv 记录未注明会议）", "2505.13271", "github.com/CycloneBoy/csc_sql"),
    "自洽投票的多数答案不一定对，且它与 pass@k 的差距随样本数扩大；常见的自我修正多只修语法错误；训练专门的挑选模型需要稀缺的标注数据。",
    ["提出 major_top2_pass@k：只看票数前两组的 pass@k，说明正确答案常在前两名中",
     "CSC：取前两组做合并修正再投票；GRPO 用于修正器和部分生成底座",
     "在 BIRD dev 的 11 个生成底座上验证（表 1：3B–70B）"],
    ["生成模型并行采 n 个 SQL（T=0.8），执行后按结果分组，取票数前两组。",
     "若候选执行结果全部一致，直接输出；否则取前两组，用合并修正模板：两条 SQL＋合并后的 schema＋各自执行结果。",
     "合并修正模型采 m=8 个新 SQL，再做一次自洽投票得到最终答案。",
     "修正训练数据：用 Qwen2.5-Coder-7B 及其 GRPO 版本在 BIRD train 上各采 8 个候选，取前两组构造。",
     "GRPO（TRL 库）：学习率 3e-6、1 个 epoch、每个提示 6 个补全；奖励见右下。"],
    [(r"R_{\mathrm{EX}}\in\{0,1\},\quad R_{\mathrm{Format}}\in\{0,1\}", "作者原式（式 1–2）"),
     (r"R=R_{\mathrm{EX}}+0.1\cdot R_{\mathrm{Format}}", "作者原式（式 3）")],
    "符号：R_EX 表示执行结果与标准 SQL 一致；R_Format 表示推理放在 <think>、答案放在 <answer> 标签中。major_top2_pass@k 为规则概括：前两组中至少一组正确即算通过。",
    "假设前两组包含可利用的正确线索；候选需有一定多样性；合并修正也可能产生新的错误。",
    [("任务与划分", "BIRD dev、BIRD 私有测试集；Spider dev/test（直接用 BIRD 上训练的模型）"),
     ("模型", "11 个开源模型（Qwen2.5-Coder、XiYanSQL-QwenCoder、OmniSQL-7B、Llama-3.1、gemma-3）；GRPO 训练 4 个生成模型与 2 个修正模型（3B、7B）"),
     ("预算", "n=4–64，m=8；三次运行取平均；训练用 4×80GB GPU；成本分析用单张 H800"),
     ("对照方法", "同模型、同 n 的自洽投票（SC）；表 3 列出 CHASE-SQL、Reasoning-SQL、Alpha-SQL 等的论文报告值"),
     ("指标", "EX；推理时间与每题费用")],
    ["CSC 相对 SC 提升 0.72–5.54 个百分点（论文所测模型与 n；CSC 另有修正采样）",
     "Qwen2.5-Coder-7B＋GRPO，n=64：SC 66.15→CSC 69.19",
     "BIRD 私有测试：71.72（7B）、73.67（32B，底座 XiYanSQL-QwenCoder-32B-2412，较底座 +4.64）",
     "未经 GRPO 的修正模型常常降低准确率；合并前 2 组优于前 1 组和前 3 组",
     "成本：32B 生成 16 个候选时，修正步骤额外增加约 7% 时间；完整流程约 0.0014 美元/题（单张 H800 租赁口径）"],
    ["可作为插件替换任意系统中的自洽投票", "小模型＋CSC 可胜过同家族大模型＋SC（如 7B 胜 14B、32B 的 SC）"],
    ["计算比 SC 多；样本多样性不足时收益小（作者自述）", "与其他方法比较用的是各论文报告数，条件不同",
     "仅在 BIRD 和 Spider 上验证；Spider dev 有个别小幅退化（表 4：−0.10 点）",
     [N("尚不能证明：在相同计算量下优于“更多采样的 SC”；本文未系统比较轨迹筛选规则"), AN]],
    "引入自适应自洽（Adaptive Self-Consistency）和软自洽（Soft Self-Consistency）以提高采样效率；把 CSC 集成进其他方法，替换其中的自洽投票组件。",
    "Sheng & Xu (2025)，正文、表 1–7 与附录 B–D",
    """CSC-SQL 详解第一页。它的出发点是一个新指标：只看票数前两组时的 pass@k。作者发现正确答案经常在前两名里，于是在候选执行结果不完全一致时，把两条 SQL 和执行结果交给一个“合并修正”模型，再采 8 个、再投票。论文对修正器和部分生成模型做 GRPO 训练，奖励是执行正确记 1、格式正确加 0.1。""",
    """第二页是实验。在 BIRD 开发集的 11 个生成底座上，CSC 均优于对应的自洽投票；但 Spider 开发集个别设置略降，例如 XiYanSQL-3B＋GRPO、n=64 时为 76.21%→76.11%。BIRD 私有测试集的 7B 结果为 71.72%。有两点值得注意：第一，修正模型如果不经过 GRPO 训练，反而常常降低准确率；第二，在 32B 生成器采 16 个候选、7B 修正器采 8 个候选的设置下，修正步骤额外增加约 7% 时间；这个比例不能推广到其他预算。局限方面，它和其他方法的比较用的是论文报告数，条件不同；作者自己也承认计算更多、依赖样本多样性。未来方向是自适应自洽和作为插件集成到别的系统。""")

detail_pages(
    "r3", "A3", "R³-SQL",
    info_rows("R³-SQL: Ranking Reward and Resampling for Text-to-SQL",
              "Hojae Han（ETRI）、Yeonseok Jeong、Seung-won Hwang（首尔大学）、Zhewei Yao、Yuxiong He（Snowflake AI Research）",
              "2026", "Findings of ACL 2026（据 arXiv 记录）", "2604.25325", None,
              "In Findings of the Association for Computational Linguistics: ACL 2026"),
    "功能等价候选的评分不一致：执行结果相同的 SQL 被打不同分；只按组大小投票，会让小而正确的组输给大而错误的组；召回有上限：候选池里没有对的 SQL 时，再好的排序也没用。",
    ["指出“功能等价候选的评分不一致”和“召回上限”两个局限", "组级排序：组间成对偏好＋组内点式效用；成对排序器用位置一致性奖励训练",
     "代理式选择性重采样；在 5 个基准上一致提升"],
    ["Arctic-Text2SQL-R1-32B 每题生成并执行 n=32 个候选（T=0.8），供代理核查。",
     "代理 f（Qwen2.5-Coder-7B，SFT）判断池中是否有正确 SQL；判断没有时采 m=1,024 个，用点式排序器保留前 32 个替换原池。",
     "执行全部候选，按结果分组。",
     "成对排序器 R³-7B（OmniSQL-7B 底座，GRPO＋一致性奖励）比较跨组候选，阈值 τ=0.05 后计 r_list。",
     "点式排序器 R³-POINT-32B 给出 r_point；按 (r_list, r_point) 字典序排序。",
     "前两组再比较一次，选胜出组内点式分最高的 SQL。"],
    [(r"r_{\mathrm{list}}(g_i)=\sum_{j\neq i}\tilde{P}(g_i>g_j),\quad r_{\mathrm{point}}(g)=|g|\cdot\max_{s\in g}\mathrm{RR}_s", "作者原式（式 3–4）"),
     (r"R=R_{\mathrm{base}}+\lambda_c R_c,\quad \lambda_c=0.5", "作者原式（式 6）")],
    "符号：P̃ 按论文式 2 的 P≥τ 记 1；其概率与“间隔”用语不一致，标为待核实；RR_s 为点式排序的倒数排名；R_base 表示偏好判断正确，R_c 表示交换输入顺序后仍正确。",
    "在当前数据库上执行结果相同，可作为分组依据，但不保证跨数据库实例的语义等价；在 BIRD 上训练的排序器判断可靠；代理能识别“池中全错”。",
    [("任务与划分", "BIRD dev（1,534）、Spider test（2,147）、Spider-DK（535）、EHRSQL（1,008）、ScienceBenchmark（299）；剔除标准 SQL 结果为空的题"),
     ("模型", "候选：Arctic-Text2SQL-R1-32B（另测 OmniSQL-7B）；排序器 R³-7B、R³-POINT-32B；代理 Qwen2.5-Coder-7B"),
     ("预算", "n=32、m=1,024；重采样在 37.01% 的题上触发；8×H200"),
     ("对照方法", "统一生成设置及适用排序器下的 CSC-SQL（简化为按组大小投票）、Contextual-SQL（点式）、CHASE-SQL（成对）、XiYan-SQL（成对＋组投票）"),
     ("指标", "EX、候选召回、R-VES、每题挑选时间、输入顺序一致性")],
    ["BIRD dev 75.03（CHASE-SQL 73.34）；5 基准平均 70.65（最好基线 68.70）",
     "4 个随机种子中最低 73.99，仍高于基线的最高值 73.27",
     "重采样让候选召回 78.80→82.72；一致性奖励使输入顺序一致性 45.60→57.49",
     "表 8 选择耗时 1.56 秒/题（CHASE-SQL 1.68）；always-resample 的 EX 在表 8/10 不一致（74.25/74.32）",
     "消融：去重采样 74.25、去执行分组 73.47；OmniSQL-7B 候选下 71.83；Spider 2.0-SQLite 29.17"],
    ["统一候选生成器和可复用排序器；重采样模块另有消融对照", "组内统一评分使分数方差为 0；论文报告选择性重采样优于始终重采样，具体成本口径仍需核实"],
    ["点式排序器依赖 BIRD 训练，领域外略逊于只用成对排序（作者自述）", "代理触发重采样的召回只有 56.02%",
     [N("1.56 秒为 SQL 选择耗时；生成、代理与重采样的计时边界未明确拆分，不能视为端到端延迟"), AN],
     "剔除空结果题，使 EX 与官方口径不完全可比"],
    "开发领域泛化的点式排序器，以减少对 BIRD 训练数据的依赖。",
    "Han et al. (2026)，正文、表 1–19 与附录 C",
    """R³-SQL 详解第一页。它针对两个问题：执行结果相同的 SQL 被打不同分，以及候选池里没有正确答案。方法分两段：先由代理判断候选池是否可能全错，必要时重采 1,024 个、保留前 32；再按执行结果分组，用成对比较的胜场 r_list 排序，平局用“组大小乘组内最佳倒数排名”的 r_point 打破。成对排序器训练时有一个一致性奖励：交换两个候选的输入顺序后判断仍正确，就额外加分。""",
    """第二页是实验。它的对比设计比较公平：作者统一了候选生成设置，并在适用时复用排序器；重采样会改变候选池，因此全系统收益不能全部归因于排序。BIRD dev 75.03，4 个随机种子都领先。需要注意三点：领域外数据上点式排序器会拖后腿；论文表 8 报告的是选择耗时 1.56 秒，未清楚拆分生成、代理与重采样的计时边界，不能当作端到端延迟；评测剔除了标准答案为空的题，所以和官方 EX 口径不完全一样。""")

detail_pages(
    "dysql", "A4", "DySQL-Bench",
    info_rows("Rethinking Text-to-SQL: Dynamic Multi-turn SQL Interaction for Real-world Database Exploration",
              "Linzhuang Sun、Tianyu Guo、Hao Liang 等 9 位（国科大、北大、清华）；通讯作者 Wentao Zhang、Bin Cui",
              "2025", "arXiv 预印本（arXiv 记录未注明会议）", "2510.26495", "github.com/Aurora-slz/Real-World-SQL-Bench"),
    "已有基准多为单轮或静态多轮、几乎只考 SELECT，缺少处理有状态执行、衡量一致性的动态评测协议。",
    ["DySQL-Bench：13 个领域、1,072 个任务，覆盖增删改查（作者称首个此类动态多轮基准）", "两阶段自动合成与校验流程，人工复核正确率 100%",
     "用户—模型—数据库三方动态评测框架"],
    ["选主表，沿外键递归取关联记录，组成一棵树（JSON）。",
     "GPT-4.1 依据树生成用户指令 I 与标准操作序列 A。",
     "验证委员会（DeepSeek-R1、Qwen3-235B，各 n 次检查全部通过）；回填缺失参数后再验；在模拟环境中检查可执行性。",
     "10 位专家逐条复核（一致性 >99.5%）。",
     "评测：Qwen2.5-72B 扮演用户；被测模型可回复或提问、执行 SQL、内部推理；用户输出 ###STOP### 或超过 30 轮即结束。"],
    [(r"\mathrm{Pass}^{k}=\mathbb{E}_{\mathrm{task}}\left[\binom{c}{k}/\binom{n}{k}\right]", "作者原式（式 1，沿用 τ-bench）"),
     (r"\mathrm{Success}=\mathbb{1}\left[\mathrm{hash}(S_2)=\mathrm{hash}(S_3)\right],\ S_3=\mathrm{execute}(A_g\,|\,S_1)", "本次整理：据第 III 节文字写成公式")],
    "符号：n 次试验中 c 次成功；S_1 初始库，S_2 模型操作后的库，S_3 执行标准操作后的库；哈希前去掉时间戳列。",
    "模拟用户能代表真实用户；最终数据库状态一致即视为完成任务，不论过程如何。",
    [("任务与划分", "13 个 SQLite 数据库（BIRD、Spider 2）；Short 561 题、Long 501 题（标准操作 <3 或 ≥3 步）"),
     ("模型", "GPT-4o、DeepSeek-V3、Qwen2.5-Max、Qwen2.5-72B、Llama-3.1-70B、OmniSQL-32B、Qwen3-32B、Qwen3-Coder-30B-A3B、Gemini-2.5-Flash"),
     ("预算", "最多 30 轮；T=0.6、top_p=0.95、top_k=20；8×H200（4 张跑模拟用户、4 张跑被测模型）；试验次数 n 未明确报告"),
     ("对照方法", "不同模型之间；零样本 vs 1–3 个示例"),
     ("指标", "各领域 Pass^1/3/5；幻觉率（编造执行结果）；对话长度与报错轮数")],
    ["GPT-4o 总体 58.34（Pass^1）、23.81（Pass^5），仅见于摘要",
     "Pass^k 随 k 下降，幅度反映重复运行的可靠性；跨模型比较混有底座和训练差异，不能单独归因于参数规模",
     "按 SQL 代码块后跟 <result> 的规则检测：幻觉率为 DeepSeek-V3 44.28%、OmniSQL-32B 26.15%、GPT-4o 0.09%",
     "3 个示例：GPT-4o 62.60→64.68、Qwen2.5-72B 63.39→65.52（3 个领域的算术平均）；这些数据不足以证明 2-shot 后饱和"],
    ["覆盖完整增删改查与动态用户，比 BIRD、CoSQL 更接近真实交互", "Pass^k 把“稳定性”变成可度量的指标"],
    ["只有一个模拟用户模型", [N("模拟用户 Qwen2.5-72B 同时是被测模型之一，且在多个领域得分最高，可能存在同家族偏差"), AN],
     "总分只在摘要出现；表中各领域题数合计 1,062，与摘要 1,072 不符",
     "任务围绕单条记录生成，偏 UPDATE 事务，较少分析型查询"],
    "引入面向 schema 的预训练或基于强化学习的适配，以提高模型在动态场景下的鲁棒性（作者在 few-shot 一节提出）。",
    "Sun et al. (2025)，正文与表 I–VI",
    """DySQL-Bench 详解第一页。它想解决的是已有基准太“静态”：要么单轮，要么多轮但历史固定，而且几乎只有 SELECT。作者用两阶段流程自动造题：先把真实数据库的记录沿外键展开成树，再让 GPT-4.1 生成用户指令和标准操作，经过两个模型校验和 10 位专家复核。评分很直接：模型操作后的数据库和执行标准操作后的数据库，哈希一致就算对。核心指标 Pass^k 沿用 τ-bench 的定义。""",
    """第二页是实验。最重要的发现是所测模型的 Pass^k 曲线均明显下降，GPT-4o 从 58% 掉到 24%。另一个有意思的现象是“编造执行结果”：论文报告 DeepSeek-V3 的幻觉率为 44.28%，检测规则是模型输出 SQL 代码块后紧跟 <result> 标签；这不是逐条事实核验后的通用幻觉率。局限方面，除了题数对不上、总分只在摘要出现之外，我们注意到模拟用户 Qwen2.5-72B 同时是被测模型，而且它在很多领域得分最高，可能存在同家族偏差，这一点论文没有讨论。""")

detail_pages(
    "birdint", "A5", "BIRD-INTERACT",
    info_rows("BIRD-INTERACT: Re-imagining Text-to-SQL Evaluation for Large Language Models via Lens of Dynamic Interactions",
              "Nan Huo、Xiaohan Xu、Jinyang Li 等 24 位（港大、Google Cloud、BIRD 团队）",
              "2025（arXiv）", "ICLR 2026 Oral", "2510.05318", "bird-interact.github.io",
              "In International Conference on Learning Representations (ICLR 2026)"),
    "已有多轮基准把历史当静态上下文或只考只读查询；常见的 LLM 模拟用户会泄露答案或偏离任务。",
    ["环境：数据库＋层级知识库＋函数驱动模拟用户", "两种评测：c-Interact 与 a-Interact", "900 个交互任务，覆盖增删改查，提供测试用例"],
    ["以单轮的 LiveSQLBench 为基础，12 位专家改造成多轮任务。",
     "注入歧义：表述歧义（意图、实现细节）、知识歧义（删除条目、切断知识链）、环境歧义（如 NULL）；每个歧义配一段澄清用的 SQL 片段。",
     "每题加一个追问子任务，依赖前一步改动后的数据库状态。",
     "模拟用户分两阶段：先把系统的提问归类为 AMB()、LOC() 或 UNA()，再依据标准 SQL 生成回答。",
     "c-Interact：澄清轮数 τ_clar=m_amb+λ_pat，每个子任务 1 次调试机会；a-Interact：9 种动作按成本扣预算 B。"],
    [(r"B=B_{\mathrm{base}}+2\,m_{\mathrm{amb}}+2\,\lambda_{\mathrm{pat}},\quad B_{\mathrm{base}}=6", "作者原式（a-Interact）"),
     (r"\tau_{\mathrm{clar}}=m_{\mathrm{amb}}+\lambda_{\mathrm{pat}}", "作者原式（c-Interact）")],
    "符号：m_amb 为标注的歧义数，λ_pat 为用户耐心（默认 3）。动作成本：执行 1、取 schema 1、查知识 0.5–1、提问 2、提交 3。SR 逐阶段累计：追问 SR 要求主任务与追问均通过测试；归一化奖励中主任务占 70%、追问占 30%。",
    "函数驱动的模拟用户能稳定代表真实用户；测试用例能判定功能等价。",
    [("任务与划分", "FULL 600 题（BI 410、DM 190）、LITE 300 题；每题 2 个子任务；PostgreSQL 14 Docker"),
     ("模型", "FULL：GPT-5、Claude-Sonnet-3.7/4、DeepSeek-Chat-V3.1、Qwen-3-Coder-480B、O3-Mini、Gemini-2.5-Pro"),
     ("预算", "λ_pat=3、B_base=6；T=0、top_p=1；每个模型单次运行；ITS 实验 λ_pat∈{0,3,5,7}"),
     ("对照方法", "模型之间；函数驱动 vs 基线模拟用户；理想化的无歧义单轮任务"),
     ("指标", "成功率 SR（主任务、追问）、归一化奖励、每任务费用（美元）；主实验模拟用户的具体底座未在正文与附录 I.3 中明确定位〔待核实〕")],
    ["FULL：完成两个子任务的比例最高 16.33%（c，Gemini-2.5-Pro）、17.00%（a，GPT-5）",
     "GPT-5 主任务 SR：c-Interact 14.50%（最差），a-Interact 29.17%（最好）",
     "LITE c-Interact 最佳为 O3-Mini，主任务 37.33%",
     "记忆嫁接：复用其他模型的澄清历史可改善 GPT-5；Lite 集 a-Interact 中 ask＋submit 占动作的 60.87%",
     "模拟用户（同 GPT-4o 底座）：UNA 失败率 22.7%→2.7%；与真人 SR 的相关系数 0.61→0.84"],
    ["降低模拟用户不当泄露答案的风险，并在抽样任务上与真人对照", "追问依赖数据库状态；预算制让“问得好”成为可度量的能力"],
    ["每个模型只跑一次（温度 0），未报告重复运行的方差估计", "包含 2 个开源大模型和 5 个闭源模型，未覆盖小模型；仅支持 PostgreSQL",
     "作者承认目前只覆盖 Text-to-SQL 领域",
     [N("尚不能证明：模拟用户与真人的一致性能推广到全部 600 题（真人对照只抽 100 题）"), AN]],
    "后训练一个本地、与人类对齐的模拟用户，降低 API 成本；在不限预算的“自由模式”下实验，并与当前“压力模式”对比；推广到 Python 代码与 API 调用生成；鼓励模型更多使用知识与 schema 检索工具。",
    "Huo et al. (2026)，正文、表 1–3、表 9–10 与附录 A、I",
    """BIRD-INTERACT 详解第一页。它由 BIRD 团队在单轮的 LiveSQLBench 上改造：故意注入歧义，并为每个歧义准备一段标准澄清；再加一个依赖前一步数据库状态的追问。模拟用户是它的关键设计：先把模型的提问归成三类——问的是标注过的歧义、合理但未标注的问题、或不该回答的问题——再生成回答，以减少不当泄露答案。两种模式里预算的公式不同，a-Interact 中每个动作都有成本。""",
    """第二页是实验。在论文所测模型中，完整任务完成率最高约为 17%。GPT-5 的主任务成功率在 c-Interact 为 14.50%（最低），在 a-Interact 为 29.17%（最高）；这个最低排名不能套用到完整任务完成率上。给 GPT-5 别的模型的澄清历史，它的成功率就明显上升，支持澄清策略是重要瓶颈的判断，但不能排除 SQL 生成能力的影响。局限是单次运行未报告重复运行方差，只测了大模型，主实验用的模拟用户模型我们还没在正文里找到，标为待核实。""")

# ================================================================ Appendix B: formulas
EXAMPLES = {
    "alpha": "教学例，非论文数据：再采 5 个 SQL，4 个与目标执行结果一致，奖励为 4/5=0.8。UCT 中，甲平均回报 0.8、访问 4 次，乙为 0.6、访问 1 次；父节点访问 5 次且 c=1.4 时，甲约 1.69、乙约 2.38，先探索乙。",
    "csc": "教学例，非论文数据：执行正确且格式正确时 R=1.1；执行错误但格式正确时 R=0.1。该奖励用于训练，并不是测试时可读取的正确性信号。",
    "r3": "教学例，非论文数据：组 A 有 4 个 SQL、最佳排名第 3，r_point=4/3≈1.33；组 B 有 2 个 SQL、最佳排名第 1，r_point=2。仅当 r_list 打平时，B 按该次级指标排在 A 前。",
    "dysql": "教学例，非论文数据：某题跑 5 次、成功 3 次，Pass^1=3/5=0.6，Pass^3=C(3,3)/C(5,3)=0.1。这是从 5 次观测无放回抽取的估计，不是已知的独立重跑成功概率。",
    "birdint": "教学例，非论文数据：3 处歧义、耐心 3 时，B=6+2×3+2×3=18。提问花 2、提交花 3、执行花 1；若只做一种动作，分别最多提问 9 次或提交 6 次，混合动作共享预算。",
}
for d in DETAILS:
    key = d["key"]
    s = new(f"附录 B｜{d['short']}：步骤、公式与演算", "公式说明")
    d["formula_page"] = s
    stack(s, 0.5, 1.12, 5.65, [("方法步骤（保留实现与训练细节）",
          [[N(f"{i + 1}. {t}")] for i, t in enumerate(d["steps"])], 11.5)], bottom=6.5)
    text(s, 6.45, 1.12, 6.38, 0.4, [[B("核心公式与符号")]], size=13, space_after=0)
    fy = 1.62
    for tex, tag in d["formulas"]:
        _, h = add_formula(s, tex, 6.5, fy, 6.2, 0.5)
        fy += max(h, 0.35) + 0.03
        text(s, 6.45, fy, 6.38, 0.27, [[G(tag)]], size=10, space_after=0)
        fy += 0.36
    # The symbol paragraph includes source uncertainties and must remain intact.
    ey = stack(s, 6.45, fy, 6.38, [(None, [[N(d["symbols"])]], 11.5)], bottom=6.5)
    text(s, 6.45, ey, 6.38, 0.4, [[B("计算示例（非论文实验）")]], size=13, space_after=0)
    text(s, 6.45, ey + 0.42, 6.38, 1.2, [[N(EXAMPLES[key])]], size=11.5, space_after=3)
    finish(s, d["src"], "本页保留方法步骤、公式来源与符号定义。\n" +
           "\n".join(f"{i + 1}. {t}" for i, t in enumerate(d["steps"])) +
           "\n" + d["symbols"] + "\n" + EXAMPLES[key])
    nav_button(s, "返回原文主图", d["method"])
    nav_button(s, "附录目录", APPX_DIV, x=0.5, w=1.4)
    nav_button(d["method"], "步骤与公式", s, x=3.0, w=2.3)
    nav_button(d["evidence"], "步骤与公式", s, x=3.0, w=2.3)

items = [
    (r"\Pr[\mathrm{any\ correct}]=1-\Pr[\mathrm{all}\ k\ \mathrm{wrong}]=1-\frac{\binom{N-C}{k}}{\binom{N}{k}}",
     "pass@k 的无偏估计（Chen et al., 2021；Brown et al., 2024 沿用）",
     "从 N 个样本（其中 C 个正确）无放回抽 k 个，全错的概率是“从 N−C 个错误样本里抽 k 个”的组合数占比。固定 N、同一策略独立同分布采样，1≤k≤N。若 N−C<k，约定分子组合数为 0；不能混用自适应补采。"),
    (r"\mathrm{Pass}^{k}=\frac{\binom{c}{k}}{\binom{n}{k}}\ \leq\ \frac{c}{n}=\mathrm{Pass}^{1}",
     "Pass^k 与 pass@k 的对比（单题无放回估计，1≤k≤n）",
     "pass@k 是“k 次里至少一次对”，随 k 上升；Pass^k 是“k 次全对”，随 k 下降。前者衡量固定预算覆盖率，后者衡量重复运行的可靠性；须固定温度与求解预算。相同协议下 pass@1＝Pass^1，不一定等于贪心解码的 EX。"),
    (r"P(g_i>g_j)=\sigma(r_i-r_j),\quad \hat{P}(g_i>g_j)=\frac{1}{|g_i||g_j|}\sum_{s_i\in g_i}\sum_{s_j\in g_j}v(s_i,s_j)",
     "R³-SQL 的 Bradley–Terry 动机与组级估计（统一记号）",
     "Bradley–Terry 模型把成对偏好看成潜在质量差的含噪观测；R³-SQL 用两组成员两两投票的平均来估计组间偏好，原文式 2 对 P≥τ=0.05 计胜场，但文字称其为偏好间隔，存在定义疑点，需结合代码核实。"),
    (r"\lim_{m\rightarrow\infty}\Pr[\mathrm{MV}_m=a^{*}]=\mathbb{1}\left[\arg\max_{a}p(a\,|\,q)=a^{*}\right]",
     "投票的极限（规则概括，本次整理）",
     "假设独立同分布、答案类别有限且唯一众数。大样本投票趋向该众数；若众数错误，则无法靠增加样本消除错误。该极限不推出约 100 次这一经验阈值。"),
]
supplement_examples = [
    "教学例：N=5、C=3、k=2，pass@2=1−C(2,2)/C(5,2)=0.9。它表示从这组观测中抽取两次至少一次答对的估计，不是单次解答准确率。",
    "教学例：同样 5 次中成功 3 次，pass@2=0.9，而 Pass^2=C(3,2)/C(5,2)=0.3。两个指标基于相同观测，却回答不同问题。",
    "教学例：两组各 2 个 SQL，4 次跨组比较中有 3 次偏好第一组，组间偏好估计为 3/4=0.75；该数不是第一组的执行准确率。",
    "教学例：若错误答案 A 的生成概率为 0.6、正确答案 B 为 0.4，增加独立样本只会让多数投票更倾向 A；更多样本不能自动修复选择偏差。",
]
for index, ((tex, head, expl), example) in enumerate(zip(items, supplement_examples), 1):
    s = new(f"附录 B｜指标与选择原理 {index}", "公式说明")
    text(s, 0.5, 1.15, 12.33, 0.65, [[B(head)]], size=18)
    add_formula(s, tex, 0.7, 2.02, 11.9, 0.75)
    rect(s, 0.5, 3.12, 6.0, 2.83, fill=CARD, rounded=True)
    text(s, 0.68, 3.27, 5.64, 0.4, [[B("含义与适用条件")]], size=14)
    text(s, 0.68, 3.85, 5.64, 1.9, [[N(expl)]], size=14, line=1.15)
    text(s, 6.85, 3.27, 5.98, 0.4, [[B("计算示例（非论文数据）")]], size=14)
    text(s, 6.85, 3.85, 5.98, 1.9, [[N(example)]], size=14, line=1.15)
    finish(s, "Chen et al. (2021)；Brown et al. (2024)；Sun et al. (2025)；Han et al. (2026)。来源与改写性质见本页说明",
           head + "\n" + expl + "\n" + example)
    nav_button(s, "附录目录", APPX_DIV)

# ================================================================ Appendix C: core interaction reading
READING = json.load(open(os.path.join(os.path.dirname(__file__), "interactive_reading.json")))
READING_PAGES = []
for figure_key, paper_name in [("mtsql", "MTSQL-R1"), ("conductor", "SQLConductor"), ("raise", "RAISE"), ("serl", "SERL-SQL")]:
    paper = next(p for p in READING["papers"] if p["name"] == paper_name)
    figure = PAPER_FIGURES[figure_key]
    s = new(f"附录 C｜{paper_name}：原文框架与可借鉴机制", "交互式 SQL")
    path = os.path.join(FIGURE_DIR, figure["image"])
    with Image.open(path) as im:
        iw, ih = im.size
    scale = min(7.7 / iw, 4.55 / ih)
    fw, fh = iw * scale, ih * scale
    fx, fy = 0.5 + (7.7 - fw) / 2, 1.62 + (4.55 - fh) / 2
    s.shapes.add_picture(path, Inches(fx), Inches(fy), Inches(fw), Inches(fh))
    lib.rec(s, "img", path, fx, fy, fw, fh)
    text(s, 0.5, 1.1, 7.7, 0.38, [[B(f"原文 Fig.{figure['figure']} · PDF 第 {figure['pdf_page']} 页")]], size=13)
    stack(s, 8.55, 1.14, 4.28, [
        ("原文机制", [[N(paper["facts"])]], 11),
        ("可借鉴", [[N(paper["borrow"])]], 11),
        ("不能直接推出", [[N(paper["boundary"])]], 11),
    ], bottom=6.5)
    finish(s, f"原图：arXiv:{paper['version']} Fig.{figure['figure']}，PDF 第 {figure['pdf_page']} 页；章节定位见原文细读文档",
           paper["facts"] + "\n" + paper["borrow"] + "\n" + paper["boundary"])
    nav_button(s, "返回主要借鉴", SLIDES[9][0])
    nav_button(s, "附录目录", APPX_DIV, x=0.5, w=1.4)
    READING_PAGES.append((paper_name, s))

# ================================================================ references
refs = [
    apa("2411.00073"),
    apa("2407.21787"),
    apa("2107.03374"),
    apa("2410.01943"),
    apa("2505.13271"),
    apa("2604.25325", "In Findings of the Association for Computational Linguistics: ACL 2026"),
    apa("2502.13550"),
    apa("2310.01798", "In International Conference on Learning Representations (ICLR 2024)", year="2024"),
    apa("2510.05318", "In International Conference on Learning Representations (ICLR 2026)", year="2026"),
    apa("2502.17248", "In Proceedings of the 42nd International Conference on Machine Learning (PMLR 267)"),
    apa("2305.03111", "In Advances in Neural Information Processing Systems 36 (NeurIPS 2023)"),
    apa("2305.20050"),
    apa("2303.17651"),
    apa("2408.06195"),
    apa("2408.03314"),
    apa("2510.26495"),
    apa("2009.10795", "In Proceedings of the 2020 Conference on Empirical Methods in Natural Language Processing (EMNLP 2020)"),
    apa("2203.11171", "In International Conference on Learning Representations (ICLR 2023)", year="2023"),
    apa("2406.12045"),
    apa("2503.14476"),
    apa("1906.02285", "In Proceedings of the 57th Annual Meeting of the Association for Computational Linguistics (ACL 2019)"),
    apa("1909.05378", "In Proceedings of the 2019 Conference on Empirical Methods in Natural Language Processing (EMNLP 2019)"),
    apa("2606.23537"),
    apa("2608.07213"),
]


def sort_key(r):
    return r.split(",")[0].lower()


refs.extend([apa("2510.12831"), apa("2506.01273"), apa("2608.00485"), apa("2306.14898")])
refs.sort(key=sort_key)
for part, chunk in enumerate([refs[i:i + 8] for i in range(0, len(refs), 8)]):
    s = new(f"参考文献（作者—年份制）{'' if part == 0 else f'（续 {part}）'}", "参考文献")
    text(s, 0.5, 1.1, 12.33, 5.85, [[N(r)] for r in chunk], size=10.5, space_after=6, line=1.05)
    finish(s, "作者与年份取自各论文 arXiv 记录；会议信息只在 arXiv 记录或论文首页注明时列出", "参考文献，供查阅。")

# Fill directory with actual page numbers; links stay valid when slide counts change.
page_number = {id(sl): i for i, (sl, _, _) in enumerate(SLIDES, 1)}
for i, d in enumerate(DETAILS):
    y = 2.05 + i * 0.72
    if i % 2 == 0:
        rect(APPX_DIV, 0.5, y, 12.33, 0.66, fill=CARD)
    text(APPX_DIV, 0.65, y + 0.08, 3.8, 0.45, [[B(d["code"] + "  " + d["short"])]], size=14, space_after=0)
    for label, field, x in [("原文主图", "method", 4.7), ("实验证据", "evidence", 7.5), ("步骤与公式", "formula_page", 10.0)]:
        target = d[field]
        shape = text(APPX_DIV, x, y + 0.08, 2.7, 0.45,
                     [[O(f"{label}  p.{page_number[id(target)]}")]], size=12, space_after=0)
        NAV.append((shape, target))
text(APPX_DIV, 0.65, 5.95, 12.0, 0.55, [[N("B 区：指标与公式。C 区：MTSQL-R1、SQLConductor、RAISE、SERL-SQL 原图与细读；最后为参考文献。")]], size=12.5)
for i, (name, target) in enumerate(READING_PAGES):
    shape = text(APPX_DIV, 0.65 + i * 3.03, 6.55, 2.93, 0.32,
                 [[O(f"{name} p.{page_number[id(target)]}")]], size=10.5, space_after=0)
    NAV.append((shape, target))

# ================================================================ finalize: footers, page numbers, notes, links
script_path = os.path.join(os.path.dirname(__file__), "speaker_script.json")
if os.path.exists(script_path):
    speaker_script = json.load(open(script_path))
    pages = speaker_script["pages"]
    if len(pages) != len(SLIDES) or speaker_script["main_pages"] != MAIN_COUNT:
        raise ValueError("Speaker script page count differs from the deck; update the transcript first.")
    for i, ((sl, src, _), entry) in enumerate(zip(SLIDES, pages), 1):
        heading = next((sh.text for sh in sl.shapes if sh.name == "Title"),
                       "交互式 Text-to-SQL 的递归自训练")
        if entry["page"] != i or entry["title"] != heading:
            raise ValueError(f"Speaker script title differs on page {i}; update the transcript first.")
        SLIDES[i - 1] = (sl, src, entry["text"])
total = len(SLIDES)
for i, (sl, src, note) in enumerate(SLIDES, 1):
    if i > 1:
        footer(sl, src, i, total)
    notes(sl, note)
for shp, key in LINKS:
    shp.click_action.target_slide = APPX[key]
for shp, target in NAV:
    shp.click_action.target_slide = target

out = os.path.join(OUT_DIR, "测试时计算与多轮TextToSQL_组会.pptx")
prs.save(out)
main_seconds = sum(entry["seconds"] for entry in pages[:MAIN_COUNT]) if os.path.exists(script_path) else 0
with open(os.path.join(OUT_DIR, "讲稿.md"), "w") as f:
    f.write("# 逐页演讲稿：交互式 Text-to-SQL 的递归自训练\n\n"
            f"对应当前 {total} 页 PPT，与 PowerPoint 演讲者备注同步。更新日期：2026-10-30。\n\n"
            f"第 1–13 页为正文，当前详讲版建议约 {round(main_seconds / 60)} 分钟，实际用时随语速和讨论调整；第 9–13 页为分步骤详讲，第 11–13 页是研究方案重点。"
            "第 14–33 页为按需展开的附录，第 34–37 页为核心交互论文原图细读，第 38–41 页为参考文献，不必连续讲完。\n\n"
            "每页开头的【建议用时】和【讲述提示】仅供演讲者参考，不用朗读；其后为可直接讲述的口语稿。"
            "论文事实沿用现有审校；研究预期以待验证假设表述，不作为项目实验结果。\n\n")
    f.write("第 9–13 页阅读路线：第 9 页讲内层交互任务；第 10 页讲文献与原项目依据；"
            "第 11 页讲内外两层循环；第 12 页讲即时与长期效用；第 13 页讲如何验证 RSI 收益。"
            "先按这五个问题理解，再读每页编号段落。\n\n")
    for i, (sl, _, note) in enumerate(SLIDES, 1):
        heading = next((sh.text for sh in sl.shapes if sh.name == "Title"),
                       "交互式 Text-to-SQL 的递归自训练" if i == 1 else "附录 A　逐篇详解")
        f.write(f"## 第 {i} 页　{heading}\n\n{note}\n\n")
# Word with screenshots is exported by render.py after fresh previews exist.
import pickle
pickle.dump([lib.REC.get(id(sl), []) for sl, _, _ in SLIDES], open(os.path.join(OUT_DIR, "layout.pkl"), "wb"))
print("saved", out, "slides", total, "main", MAIN_COUNT)
for w in lib.WARN:
    print(w)
