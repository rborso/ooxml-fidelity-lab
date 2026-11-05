"""Aggregate document scores, weighted by document class.

A mean over all documents hides the tail, and the tail is the point. Scores are
reported per class, and classes carry a usage weight: a two-point shift on a
signature page matters, the same shift in a forty-page annex does not.
"""

from __future__ import annotations

from collections import defaultdict

DEFAULT_WEIGHT = 1.0


def class_of(document: dict) -> str:
    return document.get("cls") or "unclassified"


def aggregate(documents: list[dict], weights: dict[str, float] | None = None) -> dict:
    weights = weights or {}
    buckets: dict[str, list[dict]] = defaultdict(list)
    for document in documents:
        buckets[class_of(document)].append(document)

    rows = []
    for name, docs in sorted(buckets.items()):
        scores = [float(d.get("score", 0.0)) for d in docs]
        tiers: dict[str, int] = defaultdict(int)
        for doc in docs:
            tiers[doc.get("tier", "?")] += 1
        rows.append(
            {
                "class": name,
                "count": len(docs),
                "mean": round(sum(scores) / len(scores), 4),
                "weight": float(weights.get(name, DEFAULT_WEIGHT)),
                "fatal": tiers.get("T0", 0),
                "tiers": dict(sorted(tiers.items())),
            }
        )

    total = sum(row["weight"] * row["count"] for row in rows) or 1.0
    weighted = sum(row["mean"] * row["weight"] * row["count"] for row in rows) / total
    return {"classes": rows, "weighted_mean": round(weighted, 4)}


def weights_from_config(tolerances: dict | None) -> dict[str, float]:
    data = (tolerances or {}).get("weights") or {}
    return {str(k): float(v) for k, v in (data.get("document_class") or {}).items()}
