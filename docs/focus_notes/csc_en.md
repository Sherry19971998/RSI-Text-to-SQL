# CSC-SQL (arXiv 2505.13271)

**One line:** Take the top-2 majority-vote SQL groups and let a GRPO-trained revision model merge/fix them; 71.72% EX on BIRD private test (7B), 73.67% (32B).

**How it works:**
- Sample N SQLs (T=0.8), execute, group by result.
- If the top-2 groups agree, output; else put both SQLs and results into a revision prompt.
- Revision model samples 8 new SQLs; vote again.
- Generator and reviser both trained with GRPO on BIRD train.

**Key results:** (EX %, BIRD dev unless noted)

| Setting | SC | CSC |
|---|---|---|
| Qwen2.5-Coder-7B base, n=8 | 62.18 | 64.28 |
| Qwen2.5-Coder-7B GRPO, n=8 | 64.95 | 66.96 |
| Qwen2.5-Coder-7B GRPO, n=64 | 66.15 | 69.19 |
| 7B, private test | – | 71.72 |
| 32B, private test | – | 73.67 |

**Key formula:**
- R = R_EX + 0.1 · R_Format: 1 for correct execution, +0.1 for correct output format.
- major_top2_pass@k: pass@k over only the two largest vote groups; the right answer is often there when the top-1 vote is wrong.

**Limits:**
- More inference cost than plain SC; little gain when samples lack diversity.
- Only BIRD and Spider; no multi-round training, no coverage analysis.

**For our project:**
- Same base model, T and benchmark: base 7B SC n=8 = 62.18 on dev vs our θ0 53.06 (prompts differ).
- GRPO gain shrinks as n grows (SC: +2.77 at n=8, +1.70 at n=64), matching our sharpening finding.
- Top-2 merge revision is a cheap add-on for our frontier model, or a source of repair trajectories.
