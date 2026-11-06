"""Pixel comparison of two rendered PDFs.

Text comparison answers "is the content right". It cannot see borders, fills,
images or shading, so a table whose rules changed colour scores a perfect PASS.
That is precisely the class of difference a user calls "it looks wrong", and it
was unmeasurable until now.

Both PDFs are rasterised to grayscale at 72 dpi (1 pt = 1 px) and compared per
page. Output is a change fraction plus the bounding box of the changed region,
which is enough to say *where* on the page and *how much* without pretending to
know *why*.

Deliberately dependency-free: pdftoppm emits PGM, and a PNG encoder is 20 lines
of zlib. No PIL, no numpy, nothing to pin.
"""

from __future__ import annotations

import re
import struct
import subprocess
import tempfile
import zlib
from pathlib import Path

DPI = 72
# Anti-aliasing differs between engines even when the glyphs are identical.
# 32/255 is about 12% luminance: below that is rasteriser noise, not a finding.
THRESHOLD = 32

# Bands calibrated on the corpus (325 documents, built-clean vs Word), not on
# intuition. Median changed fraction by text tier:
#
#   PASS 0.55%   T2-fonts 0.74%   T2 0.88%   T1 6.9%   FLOW 13.2%
#
# PASS tops out at 1.69%, so the line between "the font rasterises slightly
# differently" and "something visibly moved" sits at 2%. Substitutions are
# metric-compatible but never pixel-identical; treating 1% as a finding would
# have flagged every passing document.
MINOR = 0.001     # 0.1%: below any PASS document's floor
VISIBLE = 0.02    # 2%: above every PASS, below every T1 median
MAJOR = 0.08      # 8%: a block moved or an image is missing


class PixelError(RuntimeError):
    pass


def page_count(pdf: Path) -> int:
    try:
        proc = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PixelError(f"pdfinfo failed for {pdf.name}: {exc}") from exc
    match = re.search(r"^Pages:\s+(\d+)", proc.stdout, re.MULTILINE)
    if not match:
        raise PixelError(f"no page count for {pdf.name}")
    return int(match.group(1))


def _parse_pgm(data: bytes) -> tuple[int, int, bytes]:
    """P5 PGM -> (width, height, pixels). Header may contain comments."""
    tokens: list[bytes] = []
    i = 0
    while len(tokens) < 4:
        while i < len(data) and data[i : i + 1].isspace():
            i += 1
        if data[i : i + 1] == b"#":
            while i < len(data) and data[i : i + 1] != b"\n":
                i += 1
            continue
        j = i
        while j < len(data) and not data[j : j + 1].isspace():
            j += 1
        tokens.append(data[i:j])
        i = j
    if tokens[0] != b"P5":
        raise PixelError(f"not a binary PGM (magic {tokens[0]!r})")
    i += 1  # exactly one whitespace byte separates the header from the raster
    width, height = int(tokens[1]), int(tokens[2])
    pixels = data[i : i + width * height]
    if len(pixels) != width * height:
        raise PixelError(f"truncated raster: {len(pixels)} of {width * height}")
    return width, height, pixels


def render_page(pdf: Path, page: int, dpi: int = DPI) -> tuple[int, int, bytes]:
    """Rasterise one page to grayscale. 1-based page numbers, as PDF uses."""
    with tempfile.TemporaryDirectory(prefix="px-") as tmp:
        base = Path(tmp) / "p"
        try:
            subprocess.run(
                ["pdftoppm", "-gray", "-r", str(dpi), "-f", str(page), "-l", str(page),
                 "-singlefile", str(pdf), str(base)],
                capture_output=True, timeout=180, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise PixelError(f"pdftoppm failed for {pdf.name} p{page}: {exc}") from exc
        out = base.with_suffix(".pgm")
        if not out.exists():
            raise PixelError(f"pdftoppm produced nothing for {pdf.name} p{page}")
        return _parse_pgm(out.read_bytes())


def diff_pages(ref: tuple[int, int, bytes], cand: tuple[int, int, bytes],
               threshold: int = THRESHOLD) -> dict:
    """Changed fraction and bounding box between two same-size rasters."""
    rw, rh, rpx = ref
    cw, ch, cpx = cand
    if (rw, rh) != (cw, ch):
        # A different page size is not a pixel difference, it is a different
        # layout. Say so rather than comparing overlapping corners.
        return {"size": f"{cw}x{ch} != {rw}x{rh}", "fraction": 1.0,
                "bbox": None, "changed": rw * rh, "pixels": rw * rh}

    changed = 0
    min_x, min_y, max_x, max_y = rw, rh, -1, -1
    for y in range(rh):
        row = y * rw
        rrow = rpx[row : row + rw]
        crow = cpx[row : row + rw]
        if rrow == crow:  # C-level compare; most rows are identical
            continue
        for x in range(rw):
            if abs(rrow[x] - crow[x]) > threshold:
                changed += 1
                if x < min_x:
                    min_x = x
                if x > max_x:
                    max_x = x
                if y < min_y:
                    min_y = y
                if y > max_y:
                    max_y = y
    total = rw * rh
    bbox = None
    if changed:
        bbox = [round(min_x / rw, 4), round(min_y / rh, 4),
                round((max_x + 1) / rw, 4), round((max_y + 1) / rh, 4)]
    return {"size": None, "fraction": changed / total, "bbox": bbox,
            "changed": changed, "pixels": total}


def severity(fraction: float) -> str:
    if fraction <= 0.0:
        return "identical"
    if fraction < MINOR:
        return "subpixel"
    if fraction < VISIBLE:
        return "minor"
    if fraction < MAJOR:
        return "visible"
    return "major"


def compare(ref_pdf: Path, cand_pdf: Path, dpi: int = DPI,
            max_pages: int = 40) -> dict:
    """Per-page pixel comparison. Never raises: a failure is a result."""
    try:
        n_ref, n_cand = page_count(ref_pdf), page_count(cand_pdf)
    except PixelError as exc:
        return {"error": str(exc), "pages": [], "worst": 1.0, "severity": "unknown"}

    pages = []
    for number in range(1, min(n_ref, n_cand, max_pages) + 1):
        try:
            ref = render_page(ref_pdf, number, dpi)
            cand = render_page(cand_pdf, number, dpi)
        except PixelError as exc:
            pages.append({"page": number, "error": str(exc), "fraction": 1.0,
                          "severity": "unknown"})
            continue
        d = diff_pages(ref, cand)
        pages.append({"page": number, "fraction": round(d["fraction"], 6),
                      "bbox": d["bbox"], "size": d["size"],
                      "severity": severity(d["fraction"])})

    worst = max((p.get("fraction", 0.0) for p in pages), default=0.0)
    counts: dict[str, int] = {}
    for p in pages:
        counts[p["severity"]] = counts.get(p["severity"], 0) + 1
    return {
        "pages_ref": n_ref,
        "pages_cand": n_cand,
        "pages": pages,
        "worst": round(worst, 6),
        "severity": "major" if n_ref != n_cand and worst < MAJOR else severity(worst),
        "counts": counts,
    }


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def write_png(path: Path, width: int, height: int, rgb: bytearray) -> None:
    rows = bytearray()
    stride = width * 3
    for y in range(height):
        rows += b"\x00"
        rows += rgb[y * stride : (y + 1) * stride]
    png = (b"\x89PNG\r\n\x1a\n"
           + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
           + _chunk(b"IDAT", zlib.compress(bytes(rows), 6))
           + _chunk(b"IEND", b""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def write_heatmap(ref_pdf: Path, cand_pdf: Path, page: int, out: Path,
                  dpi: int = DPI, threshold: int = THRESHOLD) -> Path | None:
    """Word in grey, differences in red, overlaid for a human to look at."""
    try:
        rw, rh, rpx = render_page(ref_pdf, page, dpi)
        cw, ch, cpx = render_page(cand_pdf, page, dpi)
    except PixelError:
        return None
    if (rw, rh) != (cw, ch):
        return None

    rgb = bytearray(rw * rh * 3)
    for y in range(rh):
        row = y * rw
        o = row * 3
        for x in range(rw):
            a = rpx[row + x]
            if abs(a - cpx[row + x]) > threshold:
                rgb[o] = 255
                rgb[o + 1] = 40
                rgb[o + 2] = 40
            else:
                v = 255 - a  # ink on white, so a dark glyph stays dark
                rgb[o] = rgb[o + 1] = rgb[o + 2] = 255 - (v // 3)
            o += 3
    write_png(out, rw, rh, rgb)
    return out
