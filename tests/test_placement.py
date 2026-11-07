"""Placement checks: the three geometric defects a human spots by eye."""

from __future__ import annotations

from harness import placement


def page(number, words):
    return {"number": number, "words": [{"t": t, "b": list(b)} for t, b in words]}


def test_clean_documents_have_no_findings():
    a = {"pages": [page(1, [("hello", (50, 50, 90, 60)), ("world", (95, 50, 140, 60))])]}
    b = {"pages": [page(1, [("hello", (51, 50, 91, 60)), ("world", (96, 50, 141, 60))])]}
    result = placement.check(a, b)
    assert result["count"] == 0
    assert result["severity"] == "none"


def test_a_table_pushed_left_is_displaced():
    a = {"pages": [page(1, [("4.", (56, 496, 70, 506)), ("margin", (56, 510, 90, 520))])]}
    b = {"pages": [page(1, [("4.", (3, 496, 17, 506)), ("margin", (3, 510, 37, 520))])]}
    result = placement.check(a, b)
    kinds = [f["kind"] for f in result["findings"]]
    assert "displaced" in kinds
    moved = next(f for f in result["findings"]
                 if f["word"] == "4." and f["kind"] == "displaced")
    assert moved["dx"] == -53
    # It is also outside the area the reference uses, and that is breaking.
    assert result["severity"] == "breaking"


def test_small_jitter_is_not_a_finding():
    a = {"pages": [page(1, [("x", (50, 50, 60, 60))])]}
    b = {"pages": [page(1, [("x", (60, 50, 70, 60))])]}
    assert placement.check(a, b)["count"] == 0


def test_content_in_the_margin_is_outside():
    a = {"pages": [page(1, [("body", (55, 100, 200, 110))])]}
    b = {"pages": [page(1, [("body", (55, 100, 200, 110)), ("stray", (3, 300, 40, 310))])]}
    result = placement.check(a, b)
    assert "outside" in result["kinds"]
    assert result["severity"] == "breaking"


def test_word_leaving_the_page_is_clipped():
    a = {"pages": [page(1, [("body", (55, 100, 200, 110))])]}
    b = {"pages": [page(1, [("body", (55, 100, 200, 110)), ("edge", (-5, 300, 30, 310))])]}
    result = placement.check(a, b)
    assert "clipped" in result["kinds"]
    assert result["severity"] == "breaking"


def test_different_line_is_not_displacement():
    a = {"pages": [page(1, [("x", (50, 50, 60, 60))])]}
    b = {"pages": [page(1, [("x", (62, 90, 72, 100))])]}
    kinds = [f["kind"] for f in placement.check(a, b)["findings"]]
    assert "displaced" not in kinds


def test_findings_are_capped():
    ref_words = [(f"w{i}", (55, 100 + i * 12, 90, 110 + i * 12)) for i in range(40)]
    cand_words = [(f"w{i}", (5, 100 + i * 12, 40, 110 + i * 12)) for i in range(40)]
    result = placement.check({"pages": [page(1, ref_words)]}, {"pages": [page(1, cand_words)]})
    assert result["count"] >= 40
    assert len(result["findings"]) <= 20
