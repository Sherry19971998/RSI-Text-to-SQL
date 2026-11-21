"""Re-extract the selected original-paper diagrams from the archived source PDFs.

Requires PyMuPDF. The manifest records PDF revisions, page numbers and crop boxes.
Run from any directory: python3 docs/group_meeting_deck/src/extract_figures.py
"""
import hashlib
import json
from pathlib import Path

import fitz

root = Path(__file__).resolve().parent / "paper_figures"
manifest = json.loads((root / "manifest.json").read_text())
for key, item in manifest.items():
    source = root / item["source_pdf"]
    if hashlib.sha256(source.read_bytes()).hexdigest() != item["source_sha256"]:
        raise ValueError(f"Source PDF checksum differs: {source}")
    with fitz.open(source) as pdf:
        page = pdf[item["pdf_page"] - 1]
        page.get_pixmap(matrix=fitz.Matrix(4, 4), clip=fitz.Rect(item["crop_points"]),
                        alpha=False).save(root / item["image"])
    print(key, item["arxiv"], f"Fig. {item['figure']}")
