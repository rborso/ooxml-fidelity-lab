"""Tests for the extractor cross-check. These need no PDFs: the metric is the
part that can be wrong."""

from __future__ import annotations

from harness.crosscheck import agreement


def test_identical_streams_agree_completely():
    assert agreement(["a", "b", "c"], ["a", "b", "c"]) == 1.0


def test_order_does_not_matter():
    """This checks extraction, not reading order."""
    assert agreement(["a", "b", "c"], ["c", "b", "a"]) == 1.0


def test_missing_token_reduces_agreement():
    assert agreement(["a", "b", "c"], ["a", "b"]) == 2 / 3


def test_extra_token_reduces_agreement():
    assert agreement(["a"], ["a", "b"]) == 0.5


def test_empty_on_both_sides_is_perfect_agreement():
    assert agreement([], []) == 1.0


def test_empty_on_one_side_is_zero():
    assert agreement([], ["a"]) == 0.0
