"""Layout helpers for the group-meeting deck (python-pptx, 16:9)."""
import hashlib
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from lxml import etree
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

matplotlib.rcParams["mathtext.fontset"] = "cm"

NAVY = "23293A"
ORANGE = "C8602F"
ORANGE_LT = "F0A57E"
GRAY = "5A6170"
LGRAY = "C9CCD3"
CARD = "F3F4F6"
BLUE = "2F5D8A"
WHITE = "FFFFFF"
LATIN = "Arial"
EA = "Heiti SC"

SW, SH = 13.333, 7.5
WARN = []
REC = {}   # id(slide) -> list of drawing ops, replayed by render.py


def rec(slide, *op):
    REC.setdefault(id(slide), []).append(op)


def rgb(h):
    return RGBColor.from_string(h)


def _style_run(run, size, bold=False, color=NAVY, italic=False):
    f = run.font
    f.size = Pt(size)
    f.bold = bold
    f.italic = italic
    f.color.rgb = rgb(color)
    f.name = LATIN
    rpr = run._r.get_or_add_rPr()
    for old in rpr.findall(qn("a:ea")):
        rpr.remove(old)
    ea = etree.SubElement(rpr, qn("a:ea"))
    ea.set("typeface", EA)
    latin = rpr.find(qn("a:latin"))
    latin.addnext(ea)


def _bullet(p, level_in=0.18):
    ppr = p._p.get_or_add_pPr()
    ppr.set("marL", str(Emu(Inches(level_in))))
    ppr.set("indent", str(-Emu(Inches(level_in))))
    bf = etree.SubElement(ppr, qn("a:buFont"))
    bf.set("typeface", LATIN)
    bc = etree.SubElement(ppr, qn("a:buChar"))
    bc.set("char", "•")


def text(slide, x, y, w, h, paras, size=14, color=NAVY, bold=False, align="l",
         anchor="t", margin=0.04, space_after=4, line=1.12, name=None):
    """paras: list of paragraphs; each is str or dict(runs=[(text, opts)], bullet=bool)
    or list of (text, opts) runs."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    for side in ("left", "right", "top", "bottom"):
        setattr(tf, "margin_" + side, Inches(margin))
    tf.vertical_anchor = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE, "b": MSO_ANCHOR.BOTTOM}[anchor]
    if isinstance(paras, str):
        paras = [paras]
    norm = []
    for para in paras:
        if isinstance(para, dict):
            rs, bu = para["runs"], para.get("bullet", False)
        elif isinstance(para, str):
            rs, bu = [(para, {})], False
        else:
            rs, bu = para, False
        norm.append(([(t, o.get("size", size), o.get("bold", bold), o.get("color", color)) for t, o in rs], bu))
    rec(slide, "text", x, y, w, h, norm, align, anchor, margin, space_after, line, name or "")
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT}[align]
        p.space_after = Pt(space_after)
        p.line_spacing = line
        bullet = False
        if isinstance(para, dict):
            bullet = para.get("bullet", False)
            runs = para["runs"]
        elif isinstance(para, str):
            runs = [(para, {})]
        else:
            runs = para
        if bullet:
            _bullet(p)
        for t, o in runs:
            r = p.add_run()
            r.text = t
            _style_run(r, o.get("size", size), o.get("bold", bold), o.get("color", color), o.get("italic", False))
            if o.get("url"):
                r.hyperlink.address = o["url"]
    _check_fit(paras, w - 2 * margin, h - 2 * margin, size, line, space_after, name or str(paras)[:40])
    return tb


def _char_w(ch, pt):
    if ord(ch) > 0x2E80:
        return pt / 72.0
    if ch in "mwMW@":
        return 0.8 * pt / 72.0
    return 0.52 * pt / 72.0


def est_height(paras, width, size, line=1.12, space_after=4):
    if isinstance(paras, str):
        paras = [paras]
    total = 0.0
    for para in paras:
        if isinstance(para, dict):
            runs, ind = para["runs"], (0.18 if para.get("bullet") else 0)
        elif isinstance(para, str):
            runs, ind = [(para, {})], 0
        else:
            runs, ind = para, 0
        maxpt = max([o.get("size", size) for _, o in runs] or [size])
        wsum = sum(_char_w(c, o.get("size", size)) for t, o in runs for c in t)
        n = max(1, math.ceil(wsum / max(0.1, width - ind) * 1.04))
        total += n * maxpt * 1.2 * line / 72.0 + space_after / 72.0
    return total


def _check_fit(paras, w, h, size, line, space_after, label):
    need = est_height(paras, w, size, line, space_after)
    if need > h + 0.02:
        WARN.append(f"OVERFLOW {need:.2f}in > {h:.2f}in :: {label}")


def rect(slide, x, y, w, h, fill=CARD, line=None, rounded=False, name=None):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE,
                                 Inches(x), Inches(y), Inches(w), Inches(h))
    if rounded:
        shp.adjustments[0] = 0.06
    shp.fill.solid()
    shp.fill.fore_color.rgb = rgb(fill)
    if line:
        shp.line.color.rgb = rgb(line)
        shp.line.width = Pt(0.75)
    else:
        shp.line.fill.background()
    shp.shadow.inherit = False
    if name:
        shp.name = name
    rec(slide, "rect", x, y, w, h, fill, line, rounded)
    return shp


def hline(slide, x1, x2, y, color=NAVY, width=1.0):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y), Inches(x2), Inches(y))
    c.line.color.rgb = rgb(color)
    c.line.width = Pt(width)
    rec(slide, "line", x1, x2, y, color, width)
    return c


def arrow(slide, x, y, w, h, color=ORANGE):
    a = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x), Inches(y), Inches(w), Inches(h))
    a.fill.solid()
    a.fill.fore_color.rgb = rgb(color)
    a.line.fill.background()
    a.shadow.inherit = False
    rec(slide, "arrow", x, y, w, h, color)
    return a


FORMULA_DIR = None


def formula(tex, fontsize=20):
    """Render a mathtext formula to PNG; return (path, aspect w/h)."""
    key = hashlib.md5((tex + str(fontsize)).encode()).hexdigest()[:12]
    path = os.path.join(FORMULA_DIR, key + ".png")
    if not os.path.exists(path):
        fig = plt.figure()
        fig.text(0, 0, "$" + tex + "$", fontsize=fontsize, color="#" + NAVY)
        fig.savefig(path, dpi=300, bbox_inches="tight", pad_inches=0.02, transparent=True)
        plt.close(fig)
    from PIL import Image
    with Image.open(path) as im:
        w, h = im.size
    return path, w / h


def formula_size(tex, max_w, max_h, fontsize=20, scale=0.72):
    """Natural display size: rendered at `fontsize` pt and shown at `scale` of that, shrunk to fit."""
    path, asp = formula(tex, fontsize)
    from PIL import Image
    with Image.open(path) as im:
        pw, ph = im.size
    w, h = pw / 300.0 * scale, ph / 300.0 * scale
    k = min(1.0, max_w / w, max_h / h)
    return path, w * k, h * k


def add_formula(slide, tex, x, y, max_w, max_h, fontsize=20, scale=0.72):
    path, w, h = formula_size(tex, max_w, max_h, fontsize, scale)
    slide.shapes.add_picture(path, Inches(x), Inches(y), Inches(w), Inches(h))
    rec(slide, "img", path, x, y, w, h)
    return w, h


def title_band(slide, title, tag=None):
    rect(slide, 0, 0, SW, 0.92, fill=NAVY, name="TitleBand")
    rect(slide, 0, 0.92, SW, 0.025, fill=ORANGE)
    text(slide, 0.5, 0.12, 11.0, 0.7, [[(title, {"bold": True})]], size=22, color=WHITE, anchor="m", name="Title")
    if tag:
        text(slide, 11.4, 0.12, 1.45, 0.7, [[(tag, {})]], size=11, color=ORANGE_LT, align="r", anchor="m", name="SectionTag")


def footer(slide, src, page, total):
    if src:
        text(slide, 0.5, 7.02, 11.3, 0.36, [[(src, {})]], size=9.5, color=GRAY, anchor="m", name="Source", space_after=0)
    text(slide, 11.9, 7.02, 0.95, 0.36, [[(f"{page}/{total}", {})]], size=10, color=GRAY, align="r", anchor="m", name="PageNo", space_after=0)


def notes(slide, s):
    slide.notes_slide.notes_text_frame.text = s


def grid(slide, x, y, colw, header, rows, rowh, size=11.5, hsize=12, hh=0.42, pad=0.06, formula_h=0.5):
    """Booktabs-style table built from text boxes so formula images can sit inside cells.
    rows: list of rows; cell is paras (see text()) or dict(tex=..., paras=..., fh=...).
    Returns list of first-column shapes (for slide links)."""
    W = sum(colw)
    rect(slide, x, y, W, hh, fill=NAVY)
    cx = x
    for i, hd in enumerate(header):
        text(slide, cx, y + 0.02, colw[i], hh - 0.04, [[(hd, {"bold": True})]], size=hsize, color=WHITE, anchor="m", margin=pad, space_after=0)
        cx += colw[i]
    yy = y + hh
    hline(slide, x, x + W, yy, NAVY, 0.75)
    firsts = []
    if rowh == "auto":
        rowh = []
        for row in rows:
            best = 0.3
            for c, cell in enumerate(row):
                if isinstance(cell, dict) and "tex" in cell:
                    _, _, fh0 = formula_size(cell["tex"], colw[c] - 2 * pad, cell.get("fh", 0.75))
                    need = fh0 + est_height(cell["paras"], colw[c] - 2 * pad, size, 1.12, 2) + 0.3
                else:
                    need = est_height(cell, colw[c] - 2 * pad, size, 1.12, 2) + 0.24
                best = max(best, need)
            rowh.append(best * 1.08 + 0.04)
    for r, row in enumerate(rows):
        h = rowh[r] if isinstance(rowh, (list, tuple)) else rowh
        if r % 2 == 1:
            rect(slide, x, yy, W, h, fill=CARD)
        cx = x
        for c, cell in enumerate(row):
            if isinstance(cell, dict) and "tex" in cell:
                fh = cell.get("fh", 0.75)
                fw, fhh = add_formula(slide, cell["tex"], cx + pad, yy + 0.07, colw[c] - 2 * pad, fh)
                text(slide, cx, yy + 0.07 + fhh + 0.03, colw[c], h - fhh - 0.12, cell["paras"], size=size, margin=pad, space_after=2,
                     name=f"cell r{r}c{c}")
            else:
                shp = text(slide, cx, yy + 0.04, colw[c], h - 0.06, cell, size=size, margin=pad, space_after=2, name=f"cell r{r}c{c}")
                if c == 0:
                    firsts.append(shp)
            cx += colw[c]
        yy += h
        hline(slide, x, x + W, yy, NAVY if r == len(rows) - 1 else LGRAY, 1.5 if r == len(rows) - 1 else 0.5)
    return firsts, yy
