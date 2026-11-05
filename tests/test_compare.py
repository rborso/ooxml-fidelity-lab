"""Comparator tests. These need no renderer and no Windows: a layout tree is
just data, so the tiering logic is testable in isolation."""

from __future__ import annotations

from harness import compare


def make(texts, *, fonts=("Carlito",), dx=0.0, dy=0.0, line_count=1):
    words = [
        {"t": t, "b": [100.0 + i * 30 + dx, 100.0 + dy, 120.0 + i * 30 + dx, 112.0 + dy],
         "bl": 0, "ln": 0}
        for i, t in enumerate(texts)
    ]
    return {
        "page_count": 1,
        "pages": [{
            "number": 0, "width": 595.0, "height": 842.0,
            "words": words, "fonts": list(fonts), "line_count": line_count,
        }],
        "fonts": list(fonts),
        "producer": "test",
    }


def test_identical_passes():
    a, b = make(["alpha", "beta"]), make(["alpha", "beta"])
    assert compare.compare(a, b)["tier"] == "PASS"


def test_text_change_fails_t0():
    res = compare.compare(make(["alpha"]), make(["gamma"]))
    assert res["tier"] == "T0"
    assert res["score"] == 0.0
    assert "gamma" in res["t0"]["issues"][0]


def test_word_count_change_fails_t0():
    res = compare.compare(make(["alpha", "beta"]), make(["alpha"]))
    assert res["tier"] == "T0"


def test_geometry_shift_fails_t2():
    res = compare.compare(make(["alpha", "beta"]), make(["alpha", "beta"], dx=10.0))
    assert res["tier"] == "T2"
    assert res["t2"]["median_pt"] == 10.0


def test_small_shift_within_tolerance_passes():
    res = compare.compare(make(["alpha", "beta"]), make(["alpha", "beta"], dy=0.5))
    assert res["tier"] == "PASS"


def test_font_substitution_reported():
    res = compare.compare(
        make(["alpha"], fonts=("Georgia",)),
        make(["alpha"], fonts=("NotoSerif-Regular",)),
    )
    assert res["tier"] == "T2-fonts"
    assert res["t2"]["fonts_missing"] == ["Georgia"]
    assert res["t2"]["fonts_extra"] == ["NotoSerif-Regular"]


def test_metric_compatible_substitution_passes():
    """Calibri -> Carlito is the desired behaviour, not a finding."""
    res = compare.compare(
        make(["alpha"], fonts=("Calibri",)),
        make(["alpha"], fonts=("Carlito",)),
    )
    assert res["tier"] == "PASS"
    assert res["t2"]["fonts_expected"] == {"Calibri": "Carlito"}
    assert res["t2"]["fonts_unexpected"] == {}


def test_metric_compatible_bold_variant_passes():
    """Style suffixes must not defeat the family match."""
    res = compare.compare(
        make(["alpha"], fonts=("Calibri-Bold",)),
        make(["alpha"], fonts=("Carlito-Bold",)),
    )
    assert res["tier"] == "PASS"
    assert res["t2"]["fonts_unexpected"] == {}


def make_pages(pages, *, fonts=("Carlito",)):
    return {
        "page_count": len(pages),
        "pages": [
            {
                "number": i,
                "width": 595.0,
                "height": 842.0,
                "words": [
                    {"t": t, "b": [100.0 + j * 30, 100.0, 120.0 + j * 30, 112.0], "bl": 0, "ln": 0}
                    for j, t in enumerate(tokens)
                ],
                "fonts": list(fonts),
                "line_count": 1,
            }
            for i, tokens in enumerate(pages)
        ],
        "fonts": list(fonts),
        "producer": "test",
    }


def test_same_words_on_a_different_page_is_flow():
    """Pagination moved, nothing was lost."""
    res = compare.compare(
        make_pages([["alpha"], ["beta"]]),
        make_pages([["alpha", "beta"], []]),
    )
    assert res["tier"] == "FLOW"
    assert res["t0"]["pass"] is True
    assert res["t0"]["flow_differs"] is True


def test_word_missing_from_the_document_is_content_loss():
    res = compare.compare(
        make_pages([["alpha"], ["beta"]]),
        make_pages([["alpha"], []]),
    )
    assert res["tier"] == "T0"
    assert res["t0"]["pass"] is False


def test_reordered_content_is_order_not_data_loss():
    """Same words in a different order is a reading-order finding, not loss."""
    res = compare.compare(make(["alpha", "beta"]), make(["beta", "alpha"]))
    assert res["tier"] == "ORDER"
    assert res["t0"]["pass"] is True
    assert res["t0"]["order_differs"] is True


def test_missing_word_is_data_loss():
    res = compare.compare(make(["alpha", "beta"]), make(["alpha"]))
    assert res["tier"] == "T0"
    assert res["t0"]["pass"] is False


def test_allow_extra_downgrades_to_field():
    """A declared, expected divergence is recorded, not re-triaged."""
    res = compare.compare(
        make(["alpha"]),
        make(["alpha", "beta"]),
        {"allow_extra": True},
    )
    assert res["tier"] == "FIELD"
    assert res["t0"]["pass"] is False


def test_extra_without_tolerance_is_t0():
    res = compare.compare(make(["alpha"]), make(["alpha", "beta"]))
    assert res["tier"] == "T0"


def test_allow_missing_does_not_cover_extra():
    res = compare.compare(
        make(["alpha", "beta"]),
        make(["alpha", "gamma"]),
        {"allow_missing": True},
    )
    assert res["tier"] == "T0"


def test_page_count_mismatch_is_never_tolerated():
    res = compare.compare(
        make_pages([["alpha"]]),
        make_pages([["alpha"], ["beta"]]),
        {"allow_extra": True, "allow_missing": True},
    )
    assert res["tier"] == "T0"


def test_line_count_change_fails_t1():
    res = compare.compare(make(["alpha"], line_count=2), make(["alpha"], line_count=3))
    assert res["tier"] == "T1"
