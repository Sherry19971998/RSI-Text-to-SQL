# 最终版源码说明

当前交付 41 页，正文 13 页。最终文件清单见 `../最终版说明.md`，验证与遗留原文疑点见 `../最终版检查.json`。

## 内容组织

- 第 1–8 页：测试时计算背景、SQL 专门方法与交互维度。
- 第 9 页：用户澄清和数据库反馈的内层任务及原图依据。
- 第 10 页：交互论文机制与原项目 Phase 3 的跨轮效用问题。
- 第 11 页：内层交互求解、外层递归自训练，新模型产生下一轮数据。
- 第 12 页：即时效用 U¹ 与长期效用 Uᴴ；现有 gamma=1 时为末轮性能减起点性能。
- 第 13 页：环境接入、首批长期效用、逐轮选择规则和递归/成本对照。
- 第 14 页：附录可点击目录。
- 第 15–24 页：原有五篇 SQL 方法与交互评测论文的原图及实验证据。
- 第 25–33 页：公式、步骤及指标说明。
- 第 34–37 页：MTSQL-R1、SQLConductor、RAISE、SERL-SQL 原图细读。
- 第 38–41 页：28 条参考文献。

RSI 在本研究中操作化为参数层面的递归自训练，尚不证明改进器或训练算法自身已经增强。项目依据为根目录 README 的 Phase 3、`scripts/phase3.py`、`scripts/analyze_phase3.py` 与 `configs/phase3.yaml`。交互式用户环境接入等未完成能力继续以稿件中的限定为准。

## 重新生成

从项目根目录执行，需要 python-pptx、python-docx、matplotlib、Pillow、fonttools、lxml；提取论文图另需 PyMuPDF。

```bash
python3 docs/group_meeting_deck/src/write_speaker_script.py
MPLCONFIGDIR=/private/tmp/rsi_mpl_config python3 docs/group_meeting_deck/src/build.py docs/group_meeting_deck docs/group_meeting_deck/src/meta.json docs/group_meeting_deck/src/formulas
MPLCONFIGDIR=/private/tmp/rsi_mpl_config python3 docs/group_meeting_deck/src/render.py docs/group_meeting_deck/layout.pkl docs/group_meeting_deck/测试时计算与多轮TextToSQL_组会.pdf docs/group_meeting_deck/预览
```

这会覆盖当前交付文件。讲稿源为 `write_speaker_script.py` 中的 `SCRIPTS`，生成的 `speaker_script.json` 会与页数、标题逐页核对，再同步为 PPT 备注与 `讲稿.md`。`render.py` 在生成当前 PDF 和截图后导出 Word。

若只从当前 Markdown 和截图导出 Word：

```bash
python3 docs/group_meeting_deck/src/export_speaker_docx.py
```

`interactive_reading.json` 保存原文事实、借鉴边界和项目定位；用 `export_interactive_reading.py` 导出参考资料 Word。`paper_figures/manifest.json` 记录固定论文版本、图号、PDF 页码、裁切范围及校验值；`extract_figures.py` 可从保留的源 PDF 重新提取原图。

PDF/PNG 由布局独立渲染，并非 PowerPoint 引擎导出；中文字体依赖 macOS Heiti SC 与 Arial。公式图片绘制在卡片底色之上。Word 的 41 张截图逐张对应 `预览/s01.png` 至 `s41.png`。

最终文件已按当前状态保留，之后如在 PowerPoint 中手动编辑，再运行生成脚本会覆盖这些手动编辑；需要先将相关修改回写源码。
