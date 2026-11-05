"""Scoring tests: per-class aggregation and weighting."""

from __future__ import annotations

from harness.scoring import aggregate, weights_from_config


DOCS = [
    {"id": "a", "cls": "template", "tier": "PASS", "score": 1.0},
    {"id": "b", "cls": "template", "tier": "T1", "score": 0.25},
    {"id": "c", "cls": "annex", "tier": "PASS", "score": 1.0},
]


def test_groups_by_class():
    result = aggregate(DOCS)
    classes = {row["class"]: row for row in result["classes"]}
    assert classes["template"]["count"] == 2
    assert classes["template"]["mean"] == 0.625
    assert classes["annex"]["mean"] == 1.0


def test_counts_fatal_failures_per_class():
    docs = DOCS + [{"id": "d", "cls": "template", "tier": "T0", "score": 0.0}]
    classes = {row["class"]: row for row in aggregate(docs)["classes"]}
    assert classes["template"]["fatal"] == 1


def test_weights_change_the_overall_figure():
    unweighted = aggregate(DOCS)["weighted_mean"]
    weighted = aggregate(DOCS, {"template": 2.0})["weighted_mean"]
    assert weighted < unweighted  # the weaker class now counts double


def test_missing_class_is_unclassified():
    result = aggregate([{"id": "x", "tier": "PASS", "score": 1.0}])
    assert result["classes"][0]["class"] == "unclassified"


def test_weights_read_from_config():
    config = {"weights": {"document_class": {"template": 1.5, "annex": 0.4}}}
    assert weights_from_config(config) == {"template": 1.5, "annex": 0.4}


def test_weights_default_to_empty():
    assert weights_from_config(None) == {}
