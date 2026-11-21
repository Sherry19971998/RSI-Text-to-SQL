"""Export the primary-source reading matrix and research positioning to Word."""
import json
from pathlib import Path

from docx import Document
from docx.shared import Cm, Pt
from PIL import Image

from export_speaker_docx import font


def export():
    root = Path(__file__).resolve().parents[1]
    data = json.loads((root / "src/interactive_reading.json").read_text())
    doc = Document()
    doc.core_properties.title = "交互式 SQL：原文细读、RSI 主线与 idea 依据"
    doc.core_properties.language = "zh-CN"
    section = doc.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.top_margin = section.bottom_margin = Cm(2)
    section.left_margin = section.right_margin = Cm(2.2)
    for name, size in [("Normal", 11), ("Title", 20), ("Heading 1", 15), ("Heading 2", 12)]:
        font(doc.styles[name], size, bold=name != "Normal")
    doc.styles["Normal"].paragraph_format.line_spacing = 1.35
    doc.styles["Normal"].paragraph_format.space_after = Pt(7)
    doc.add_paragraph("交互式 SQL\n原文细读、RSI 主线与 idea 依据", "Title")
    doc.add_paragraph(f"核对日期：{data['date']}。{data['scope']}")
    doc.add_paragraph("核查结论与更正", "Heading 1")
    for text in data["corrections"]:
        doc.add_paragraph(text, "List Bullet")
    doc.add_paragraph("逐篇细读：原文机制、可借鉴内容与边界", "Heading 1")
    for paper in data["papers"]:
        doc.add_paragraph(f"{paper['name']} · {paper['version']}", "Heading 2")
        doc.add_paragraph(paper["role"])
        doc.add_paragraph("定位章节：" + paper["sections"])
        doc.add_paragraph("原文：" + paper["url"])
        key = {"BIRD-INTERACT": "birdint", "MTSQL-R1": "mtsql", "SQLConductor": "conductor",
               "RAISE": "raise", "SERL-SQL": "serl"}.get(paper["name"])
        if key:
            figures = root / "src/paper_figures"
            entry = json.loads((figures / "manifest.json").read_text())[key]
            image_path = figures / entry["image"]
            with Image.open(image_path) as image:
                width, height = image.size
            doc.add_picture(str(image_path), width=Cm(min(16.4, 10 * width / height)))
            doc.add_paragraph(f"原文 Fig.{entry['figure']}，PDF 第 {entry['pdf_page']} 页。原图裁切，未重绘。")
        for label, key in [("原文机制", "facts"), ("可借鉴", "borrow"),
                           ("不能据此声称", "boundary"), ("建议验证", "test")]:
            p = doc.add_paragraph()
            p.add_run(label + "：").bold = True
            p.add_run(paper[key])
    doc.add_paragraph("我们的候选方案与验证路径", "Heading 1")
    labels = {"status": "方案状态", "question": "研究问题", "interaction": "交互过程",
              "learning": "学习对象", "novelty_boundary": "新颖性边界", "evaluation": "评测",
              "training_data": "训练与评测数据"}
    for key, label in labels.items():
        p = doc.add_paragraph()
        p.add_run(label + "：").bold = True
        p.add_run(data["proposal"][key])
    if "rsi_evidence" in data:
        doc.add_paragraph("RSI 的项目操作定义与代码依据", "Heading 1")
        doc.add_paragraph(data["rsi_evidence"]["operational_definition"])
        for source in data["rsi_evidence"]["project_sources"]:
            doc.add_paragraph(source, "List Bullet")
    doc.add_paragraph("当前实现与计划的差距", "Heading 1")
    for text in data["implementation"]:
        doc.add_paragraph(text, "List Bullet")
    doc.add_paragraph("阅读范围", "Heading 1")
    doc.add_paragraph("本次对照以上固定版本原文的方法、训练、任务协议与相关实验/消融部分，核查借鉴关系与重合。未独立复现实验，未进行全面新颖性检索；旧材料中的原文疑点继续保留。")
    out = root / "交互式SQL_原文细读与idea依据.docx"
    doc.save(out)
    return out


if __name__ == "__main__":
    print(export())
