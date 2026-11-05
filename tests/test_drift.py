"""Drift tests. Payloads are synthetic; reference drift needs PDFs and is
covered by the empty case here."""

from __future__ import annotations

from pathlib import Path

from harness.drift import reference_drift, score_drift


def payload(docs, started="20260101T000000Z"):
    return {"started": started, "documents": docs}


A = payload([
    {"id": "x", "cls": "template", "tier": "T1", "score": 0.25},
    {"id": "y", "cls": "annex", "tier": "PASS", "score": 1.0},
])

B = payload([
    {"id": "x", "cls": "template", "tier": "PASS", "score": 1.0},
    {"id": "y", "cls": "annex", "tier": "PASS", "score": 1.0},
])


def test_detects_tier_change():
    result = score_drift(A, B)
    assert result["changes"] == [
        {"id": "x", "before": "T1", "after": "PASS", "delta": 0.75}
    ]


def test_reports_class_delta():
    classes = {row["class"]: row for row in score_drift(A, B)["classes"]}
    assert classes["template"]["delta"] == 0.75
    assert classes["annex"]["delta"] == 0.0


def test_unchanged_runs_produce_no_changes():
    assert score_drift(A, A)["changes"] == []


def test_reference_drift_without_pdfs_is_empty():
    result = reference_drift(Path("/nonexistent"), Path("/nonexistent"), A, B)
    assert result["documents"] == 0
    assert result["mean"] is None
