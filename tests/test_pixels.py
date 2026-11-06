"""Pixel tier: parsing, diffing, severity, and a PNG that is actually a PNG."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

import pytest

from harness import pixels


def _pgm(width: int, height: int, fill: int = 255, comment: bytes = b"") -> bytes:
    header = b"P5\n"
    if comment:
        header += comment + b"\n"
    header += f"{width} {height}\n255\n".encode()
    return header + bytes([fill]) * (width * height)


def test_parse_pgm_basic():
    w, h, px = pixels._parse_pgm(_pgm(4, 3, 7))
    assert (w, h) == (4, 3)
    assert px == bytes([7]) * 12


def test_parse_pgm_with_comment():
    w, h, px = pixels._parse_pgm(_pgm(2, 2, 9, b"# created by pdftoppm"))
    assert (w, h) == (2, 2)
    assert len(px) == 4


def test_parse_pgm_rejects_other_magic():
    with pytest.raises(pixels.PixelError):
        pixels._parse_pgm(b"P6\n1 1\n255\n\x00\x00\x00")


def test_identical_pages_are_zero():
    page = (3, 2, bytes([10] * 6))
    d = pixels.diff_pages(page, page)
    assert d["fraction"] == 0.0
    assert d["changed"] == 0
    assert d["bbox"] is None


def test_one_changed_pixel_has_bbox():
    ref = (4, 4, bytes([255] * 16))
    cand = bytearray(ref[2])
    cand[5] = 0  # x=1, y=1
    d = pixels.diff_pages(ref, (4, 4, bytes(cand)))
    assert d["changed"] == 1
    assert d["fraction"] == pytest.approx(1 / 16)
    assert d["bbox"] == [0.25, 0.25, 0.5, 0.5]


def test_below_threshold_is_ignored():
    ref = (2, 1, bytes([100, 100]))
    # Strictly greater: a delta exactly at the threshold is rasteriser noise.
    cand = (2, 1, bytes([100 + pixels.THRESHOLD, 100]))
    assert pixels.diff_pages(ref, cand)["changed"] == 0
    cand2 = (2, 1, bytes([100 + pixels.THRESHOLD + 1, 100]))
    assert pixels.diff_pages(ref, cand2)["changed"] == 1


def test_size_mismatch_is_not_a_corner_compare():
    d = pixels.diff_pages((2, 2, bytes(4)), (3, 2, bytes(6)))
    assert d["fraction"] == 1.0
    assert d["size"] == "3x2 != 2x2"


def test_severity_bands():
    assert pixels.severity(0.0) == "identical"
    assert pixels.severity(0.0001) == "subpixel"
    assert pixels.severity(0.005) == "minor"
    assert pixels.severity(0.02) == "visible"
    assert pixels.severity(0.5) == "major"


def test_write_png_is_a_png(tmp_path: Path):
    out = tmp_path / "x.png"
    pixels.write_png(out, 2, 2, bytearray([255] * 12))
    data = out.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    width, height = struct.unpack(">II", data[16:24])
    assert (width, height) == (2, 2)
    # The IDAT must inflate to scanlines with a filter byte each.
    start = data.index(b"IDAT") + 4
    end = data.index(b"IEND") - 8
    raw = zlib.decompress(data[start:end])
    assert len(raw) == 2 * (1 + 2 * 3)


def test_pattern_separates_raster_from_structure():
    # Thin ink spread over a wide box: a substituted font.
    assert pixels.pattern(0.05, 100) == "diffuse"
    # Most of a small box changed: a moved block or a missing image.
    assert pixels.pattern(0.60, 100) == "concentrated"
    assert pixels.pattern(0.0, 0) == "none"


def test_density_is_measured_in_the_bbox():
    ref = (10, 10, bytes([255] * 100))
    cand = bytearray(ref[2])
    for x in range(4):          # a 4x1 line -> bbox area 4
        cand[x] = 0
    d = pixels.diff_pages(ref, (10, 10, bytes(cand)))
    assert d["changed"] == 4
    assert d["density"] == pytest.approx(1.0)
    assert pixels.pattern(d["density"], d["changed"]) == "concentrated"
