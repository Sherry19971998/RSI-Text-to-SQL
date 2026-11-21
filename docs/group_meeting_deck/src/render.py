"""Replay the recorded slide layout into a PDF (and PNGs for QA) with measured line wrapping.

Usage: python render.py layout.pkl out.pdf png_dir
"""
import pickle
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.font_manager import FontProperties
from matplotlib.patches import FancyBboxPatch, Polygon, Rectangle
from fontTools.ttLib import TTCollection

for p in ["/System/Library/Fonts/Hiragino Sans GB.ttc", "/System/Library/Fonts/STHeiti Medium.ttc",
          "/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]:
    fm.fontManager.addfont(p)
matplotlib.rcParams["pdf.fonttype"] = 42

SW, SH = 13.333, 7.5
PROPS = {}
# Use TrueType outlines: Hiragino CFF outlines render incorrectly when embedded as Type 42.
FONT_CACHE = Path('/private/tmp/rsi_deck_font_cache')
FONT_CACHE.mkdir(exist_ok=True)
for name, source in [("regular", "STHeiti Light.ttc"), ("bold", "STHeiti Medium.ttc")]:
    path = FONT_CACHE / (name + "_heiti_v2.ttf")
    if not path.exists():
        font = TTCollection("/System/Library/Fonts/" + source).fonts[1]
        for table in ("feat", "morx"):
            if table in font:
                del font[table]
        font.save(path)


def prop(size, bold, cjk=False):
    k = (size, bold, cjk)
    if k not in PROPS:
        if cjk:
            PROPS[k] = FontProperties(fname=str(FONT_CACHE / ("bold_heiti_v2.ttf" if bold else "regular_heiti_v2.ttf")), size=size)
        else:
            PROPS[k] = FontProperties(fname="/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf", size=size)
    return PROPS[k]


NO_START = set("，。、；：？！）】》」』”’%·…—,.;:?!)")
NO_END = set("（【《「『“‘(")


def is_cjk(ch):
    return ord(ch) > 0x2E80 or 0x2460 <= ord(ch) <= 0x24FF or ch == '∈'


def tokens(runs):
    """Split runs into breakable tokens: each CJK char alone; Latin words keep trailing space."""
    out = []
    for t, size, bold, color in runs:
        buf = ""
        for ch in t:
            if is_cjk(ch):
                if buf:
                    out.append((buf, size, bold, color))
                    buf = ""
                out.append((ch, size, bold, color))
            elif ch == " ":
                buf += ch
                out.append((buf, size, bold, color))
                buf = ""
            elif ch == "\n":
                if buf:
                    out.append((buf, size, bold, color))
                    buf = ""
                out.append(("\n", size, bold, color))
            else:
                buf += ch
        if buf:
            out.append((buf, size, bold, color))
    return out


def split_script(s):
    out, buf, mode = [], "", None
    for ch in s:
        c = is_cjk(ch)
        if mode is None or c == mode:
            buf += ch
        else:
            out.append(buf)
            buf = ch
        mode = c
    if buf:
        out.append(buf)
    return out


class Measurer:
    def __init__(self, fig):
        self.r = fig.canvas.get_renderer()
        self.dpi = fig.dpi
        self.cache = {}

    def w(self, s, size, bold):
        k = (s, size, bold)
        if k not in self.cache:
            px = self.r.get_text_width_height_descent(s, prop(size, bold, len(s) == 1 and is_cjk(s)), ismath=False)[0]
            self.cache[k] = px / self.dpi
        return self.cache[k]


def layout_para(m, runs, bullet, width):
    ind = 0.18 if bullet else 0.0
    toks = tokens(runs)
    lines, cur, cw = [], [], 0.0
    avail = width - ind
    for tk in toks:
        if tk[0] == "\n":
            lines.append(cur)
            cur, cw = [], 0.0
            continue
        tw = m.w(tk[0], tk[1], tk[2])
        if cur and cw + m.w(tk[0].rstrip(), tk[1], tk[2]) > avail and tk[0][0] not in NO_START:
            carry = []
            while cur and cur[-1][0][-1] in NO_END:
                carry.insert(0, cur.pop())
            lines.append(cur)
            cur, cw = carry, sum(m.w(c[0], c[1], c[2]) for c in carry)
            if tk[0].strip() == "":
                continue
        cur.append(tk)
        cw += tw
    lines.append(cur)
    return lines, ind


def draw_text(ax, m, op, warns, page):
    _, x, y, w, h, paras, align, anchor, margin, space_after, line, name = op
    iw = w - 2 * margin
    blocks, total = [], 0.0
    for runs, bullet in paras:
        lines, ind = layout_para(m, runs, bullet, iw)
        maxpt = max([r[1] for r in runs] or [12])
        lh = maxpt * 1.2 * line / 72.0
        blocks.append((lines, ind, lh, bullet, maxpt))
        total += lh * len(lines) + space_after / 72.0
    total -= space_after / 72.0
    avail = h - 2 * margin
    if total > avail + 0.03:
        warns.append(f"p{page}: text overflow {total:.2f}in > {avail:.2f}in :: {name or paras[0][0][0][0][:30]}")
    ty = y + margin
    if anchor == "m":
        ty += max(0.0, (avail - total) / 2)
    elif anchor == "b":
        ty += max(0.0, avail - total)
    for lines, ind, lh, bullet, maxpt in blocks:
        for li, ln in enumerate(lines):
            lw = sum(m.w(t[0], t[1], t[2]) for t in ln)
            if ln:
                lw -= m.w(ln[-1][0], ln[-1][1], ln[-1][2]) - m.w(ln[-1][0].rstrip(), ln[-1][1], ln[-1][2])
            lx = x + margin + ind
            if align == "c":
                lx = x + margin + (iw - lw) / 2
            elif align == "r":
                lx = x + w - margin - lw
            base = ty + lh * 0.5 + maxpt / 72.0 * 0.36
            if bullet and li == 0:
                ax.text(x + margin, base, "•", fontproperties=prop(maxpt, False), color="#" + (ln[0][3] if ln else "23293A"), va="baseline", parse_math=False)
            # merge consecutive same-style tokens
            segs = []
            for t in ln:
                if segs and segs[-1][1:] == t[1:]:
                    segs[-1] = (segs[-1][0] + t[0],) + t[1:]
                else:
                    segs.append(t)
            cx = lx
            for s, size, bold, color in segs:
                for piece in split_script(s):
                    ax.text(cx, base, piece, fontproperties=prop(size, bold, is_cjk(piece[0])), color="#" + color, va="baseline", parse_math=False)
                    cx += m.w(piece, size, bold) if not (len(piece) > 1 and is_cjk(piece[0])) else sum(m.w(ch, size, bold) for ch in piece)
            ty += lh
        ty += space_after / 72.0


def render(layout, pdf_path, png_dir):
    warns = []
    if png_dir:
        Path(png_dir).mkdir(parents=True, exist_ok=True)
    with PdfPages(pdf_path) as pdf:
        for i, ops in enumerate(layout, 1):
            fig = plt.figure(figsize=(SW, SH), dpi=100)
            ax = fig.add_axes([0, 0, 1, 1])
            ax.set_xlim(0, SW)
            ax.set_ylim(SH, 0)
            ax.axis("off")
            fig.patch.set_facecolor("white")
            m = Measurer(fig)
            for op in ops:
                kind = op[0]
                if kind == "rect":
                    _, x, y, w, h, fill, line, rounded = op
                    if rounded:
                        r = min(w, h) * 0.06
                        patch = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                               facecolor="#" + fill, edgecolor="#" + line if line else "none", linewidth=0.75)
                    else:
                        patch = Rectangle((x, y), w, h, facecolor="#" + fill, edgecolor="#" + line if line else "none", linewidth=0.75)
                    ax.add_patch(patch)
                elif kind == "line":
                    _, x1, x2, y, color, width = op
                    ax.plot([x1, x2], [y, y], color="#" + color, linewidth=width, solid_capstyle="butt")
                elif kind == "arrow":
                    _, x, y, w, h, color = op
                    pts = [(x, y + h * 0.25), (x + w * 0.55, y + h * 0.25), (x + w * 0.55, y), (x + w, y + h / 2),
                           (x + w * 0.55, y + h), (x + w * 0.55, y + h * 0.75), (x, y + h * 0.75)]
                    ax.add_patch(Polygon(pts, closed=True, facecolor="#" + color, edgecolor="none"))
                elif kind == "img":
                    _, path, x, y, w, h = op
                    # Images must sit above background patches (default zorder=1).
                    # Otherwise formulas on shaded cards/rows disappear in PDF/PNG.
                    ax.imshow(mpimg.imread(path), extent=[x, x + w, y + h, y], aspect="auto", interpolation="antialiased", zorder=2)
                elif kind == "text":
                    draw_text(ax, m, op, warns, i)
            ax.set_xlim(0, SW)
            ax.set_ylim(SH, 0)
            pdf.savefig(fig)
            if png_dir:
                fig.savefig(f"{png_dir}/s{i:02d}.png", dpi=120)
            plt.close(fig)
    return warns


if __name__ == "__main__":
    layout = pickle.load(open(sys.argv[1], "rb"))
    for w in render(layout, sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None):
        print(w)
    print("rendered", len(layout))
    if len(sys.argv) > 3:
        transcript = Path(sys.argv[2]).parent / "讲稿.md"
        if transcript.is_file():
            from export_speaker_docx import export
            print("exported", export(transcript))
