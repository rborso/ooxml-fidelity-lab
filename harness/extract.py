"""Extract a normalized layout tree from a PDF.

The tree is the unit of comparison. It is deliberately boring: words with
bounding boxes, per-line structure, and the font names actually used. Pixels are
never compared at this layer.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pymupdf

SUBSET_PREFIX = re.compile(r"^[A-Z]{6}\+")


def normalize_font(name: str) -> str:
    """Strip the subset prefix so 'BAAAAA+Carlito-Bold' == 'Carlito-Bold'."""
    return SUBSET_PREFIX.sub("", name or "")


def _r(value: float) -> float:
    return round(float(value), 2)


def extract_layout(pdf_path: Path) -> dict:
    doc = pymupdf.open(pdf_path)
    pages = []
    all_fonts = set()

    for page in doc:
        fonts = {normalize_font(f[3]) for f in page.get_fonts()}
        all_fonts |= fonts

        # words: (x0, y0, x1, y1, text, block_no, line_no, word_no)
        raw = page.get_text("words")
        words = [
            {
                "t": w[4],
                "b": [_r(w[0]), _r(w[1]), _r(w[2]), _r(w[3])],
                "bl": int(w[5]),
                "ln": int(w[6]),
            }
            for w in raw
        ]
        line_keys = {(w["bl"], w["ln"]) for w in words}

        pages.append(
            {
                "number": page.number,
                "width": _r(page.rect.width),
                "height": _r(page.rect.height),
                "words": words,
                "fonts": sorted(fonts),
                "line_count": len(line_keys),
            }
        )

    tree = {
        "page_count": doc.page_count,
        "pages": pages,
        "fonts": sorted(all_fonts),
        "producer": (doc.metadata or {}).get("producer", ""),
    }
    doc.close()
    return tree


def canonical(tree: dict) -> str:
    return json.dumps(tree, sort_keys=True, separators=(",", ":"))


def layout_hash(tree: dict) -> str:
    return hashlib.sha256(canonical(tree).encode()).hexdigest()


def line_signature(page: dict) -> list[str]:
    """The last word on each line, in order. Catches line-break drift."""
    lines: dict[tuple, str] = {}
    for w in page["words"]:
        lines[(w["bl"], w["ln"])] = w["t"]
    return [lines[k] for k in sorted(lines)]


def page_text(page: dict) -> list[str]:
    return [w["t"] for w in page["words"]]
