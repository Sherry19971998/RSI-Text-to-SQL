"""Export the page-aligned Markdown transcript to a readable Word document.

Usage: python3 docs/group_meeting_deck/src/export_speaker_docx.py
"""
from pathlib import Path
import re

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


def font(style, size, color="23293A", bold=False):
    style.font.name = "Arial"
    style.font.size = Pt(size)
    style.font.bold = bold
    style.font.color.rgb = RGBColor.from_string(color)
    fonts = style.element.get_or_add_rPr().get_or_add_rFonts()
    fonts.set(qn("w:eastAsia"), "宋体")


def export(markdown_path, output_path=None):
    markdown_path = Path(markdown_path)
    output_path = Path(output_path or markdown_path.with_suffix(".docx"))
    text = markdown_path.read_text()
    headings = re.findall(r"^## 第 (\d+) 页[^\n]*", text, re.MULTILINE)
    images = {int(page): markdown_path.parent / "预览" / f"s{int(page):02d}.png"
              for page in headings}
    missing = [str(path) for path in images.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("Generate the slide previews before exporting Word: " + ", ".join(missing))
    doc = Document()
    doc.core_properties.title = "逐页演讲稿：交互式 Text-to-SQL 的递归自训练"
    doc.core_properties.subject = f"{len(headings)} 页组会 PPT 的正文讲述与附录备用讲稿"
    doc.core_properties.language = "zh-CN"
    section = doc.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.top_margin = section.bottom_margin = Cm(2)
    section.left_margin = section.right_margin = Cm(2.3)
    section.header_distance = section.footer_distance = Cm(0.9)

    font(doc.styles["Normal"], 11)
    body = doc.styles["Normal"].paragraph_format
    body.line_spacing = 1.4
    body.space_after = Pt(7)
    body.widow_control = True
    font(doc.styles["Title"], 22, bold=True)
    font(doc.styles["Heading 1"], 15, bold=True)
    heading = doc.styles["Heading 1"].paragraph_format
    heading.space_before, heading.space_after = Pt(18), Pt(9)
    heading.keep_with_next = True
    heading.page_break_before = True
    font(doc.styles["Heading 2"], 12, bold=True)
    detail = doc.styles["Heading 2"].paragraph_format
    detail.space_before, detail.space_after = Pt(11), Pt(5)
    detail.keep_with_next = True
    font(doc.styles["Caption"], 9.5, color="5A6170")
    cue = doc.styles["Caption"].paragraph_format
    cue.space_after = Pt(4)
    cue.line_spacing = 1.2
    cue.keep_with_next = True

    header = section.header.paragraphs[0]
    header.text = "组会逐页演讲稿  ·  RSI Text-to-SQL"
    header.style = doc.styles["Caption"]
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer.add_run("第 ")
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    footer._p.append(field)
    footer.add_run(" 页")

    for block in re.split(r"\n\s*\n", text.strip()):
        if block.startswith("# "):
            doc.add_paragraph(block[2:].strip(), style="Title")
        elif block.startswith("## "):
            doc.add_paragraph(block[3:].strip(), style="Heading 1")
            page = int(re.match(r"## 第 (\d+) 页", block).group(1))
            picture = doc.add_paragraph()
            picture.alignment = WD_ALIGN_PARAGRAPH.CENTER
            picture.paragraph_format.line_spacing = 1
            picture.paragraph_format.space_after = Pt(9)
            picture.paragraph_format.keep_with_next = True
            width = section.page_width - section.left_margin - section.right_margin
            shape = picture.add_run().add_picture(str(images[page]), width=width)
            shape._inline.docPr.set("descr", f"PPT 第 {page} 页：{block[3:].strip()}")
        elif block.startswith("【"):
            for line in block.splitlines():
                doc.add_paragraph(line, style="Caption")
        elif re.fullmatch(r"\d+）[^\n]+", block):
            doc.add_paragraph(block, style="Heading 2")
        else:
            doc.add_paragraph(block)
    doc.save(output_path)
    return output_path


if __name__ == "__main__":
    print(export(Path(__file__).resolve().parents[1] / "讲稿.md"))
