"""Compare two runs.

Two questions, deliberately separate:

  score drift      - did the renderer change against the same reference?
  reference drift  - did the reference itself change, i.e. did Word drift?

The second is the one nobody has a number for. If Word moves between builds,
"fidelity to Word" is undefined until you measure how much Word moves.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .compare import page_tokens
from .crosscheck import agreement
from .extract import extract_layout
from .scoring import aggregate


def load(run_dir: Path) -> dict:
    return json.loads((run_dir / "results.json").read_text())


def _tokens(pdf: Path) -> list[str]:
    if not pdf.exists():
        return []
    tree = extract_layout(pdf)
    return [token for page in tree["pages"] for token in page_tokens(page)]


def score_drift(a: dict, b: dict) -> dict:
    """Renderer change between two runs, per document and per class."""
    left = {d["id"]: d for d in a.get("documents", [])}
    right = {d["id"]: d for d in b.get("documents", [])}

    changes = []
    for doc_id in sorted(set(left) & set(right)):
        before, after = left[doc_id], right[doc_id]
        delta = round(float(after.get("score", 0)) - float(before.get("score", 0)), 4)
        if delta or before.get("tier") != after.get("tier"):
            changes.append(
                {
                    "id": doc_id,
                    "before": before.get("tier"),
                    "after": after.get("tier"),
                    "delta": delta,
                }
            )

    classes_before = {row["class"]: row["mean"] for row in aggregate(a.get("documents", []))["classes"]}
    classes_after = {row["class"]: row["mean"] for row in aggregate(b.get("documents", []))["classes"]}
    per_class = [
        {
            "class": name,
            "before": classes_before.get(name),
            "after": classes_after.get(name),
            "delta": round((classes_after.get(name, 0) - classes_before.get(name, 0)), 4),
        }
        for name in sorted(set(classes_before) | set(classes_after))
    ]

    return {"changes": changes, "classes": per_class}


def reference_drift(a_dir: Path, b_dir: Path, a: dict, b: dict) -> dict:
    """Word versus Word: token agreement between the two reference PDFs."""
    left = {d["id"] for d in a.get("documents", [])}
    right = {d["id"] for d in b.get("documents", [])}
    rows = []
    for doc_id in sorted(left & right):
        pdf_a = a_dir / "ref" / doc_id / "document.pdf"
        pdf_b = b_dir / "ref" / doc_id / "document.pdf"
        if not pdf_a.exists() or not pdf_b.exists():
            continue
        rows.append(
            {
                "id": doc_id,
                "agreement": round(agreement(_tokens(pdf_a), _tokens(pdf_b)), 5),
            }
        )
    if not rows:
        return {"documents": 0, "mean": None, "rows": []}
    return {
        "documents": len(rows),
        "mean": round(sum(r["agreement"] for r in rows) / len(rows), 5),
        "rows": rows,
    }
