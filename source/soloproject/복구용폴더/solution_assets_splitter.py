# -*- coding: utf-8 -*-
"""
solution assets splitter (text-block based + blank-strip filter)
Drop-in helper for your 1_parser.py.

Usage:
    from solution_assets_splitter import render_solution_images
"""
import re
from pathlib import Path

import fitz  # PyMuPDF


def _ink_ratio(pix: fitz.Pixmap) -> float:
    """
    Returns ratio of non-white pixels (rough "ink") in the rendered pixmap.
    Used to skip blank/near-blank strips.
    """
    import numpy as np

    img = np.frombuffer(pix.samples, dtype=np.uint8)
    if pix.n >= 3:
        img = img.reshape(pix.h, pix.w, pix.n)[..., :3]
        gray = img.mean(axis=2)
    else:
        gray = img.reshape(pix.h, pix.w)

    return float((gray < 245).sum()) / float(gray.size)


def render_solution_images(
    pdf_path: str,
    out_dir: Path,
    *,
    dpi: int = 200,
    min_ink_ratio: float = 0.002,
):
    """
    Solution-only renderer:
        - Finds blocks containing leading "N." (question number) on each page
        - Crops to that block rectangle
        - Skips blank/near-blank crops via ink ratio
    Returns:
        dict[int, list[dict]]  # qnum -> list of asset dicts
    Asset dict:
        {"type":"solution_image", "path":"...", "page": 1-based}
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    assets_by_q = {}

    try:
        for pno in range(len(doc)):
            page = doc[pno]
            blocks = page.get_text("blocks")  # (x0,y0,x1,y1, "text", block_no, block_type)

            for b in blocks:
                x0, y0, x1, y1, text, *_ = b
                if not text:
                    continue
                t = text.strip()
                if not t:
                    continue

                # match "5." at start (allow spaces)
                m = re.match(r"^\s*(\d+)\.\s*", t)
                if not m:
                    continue

                qnum = int(m.group(1))

                rect = fitz.Rect(x0, y0, x1, y1) & page.rect
                if rect.is_empty or rect.width <= 1 or rect.height <= 1:
                    continue

                pix = page.get_pixmap(clip=rect, dpi=dpi)
                if pix.width <= 0 or pix.height <= 0:
                    continue

                if _ink_ratio(pix) < min_ink_ratio:
                    # too blank => skip (prevents white strips)
                    continue

                # deterministic filename
                img_path = out_dir / f"solution_image_q{qnum:02d}_p{pno+1}.png"
                pix.save(str(img_path))

                assets_by_q.setdefault(qnum, []).append(
                    {"type": "solution_image", "path": str(img_path).replace("\\", "/"), "page": pno + 1}
                )
    finally:
        doc.close()

    return assets_by_q
