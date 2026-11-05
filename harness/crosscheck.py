"""Cross-check the PDF text extractor against a second implementation.

If the measurement pipeline has a bug, every score downstream is wrong and
nothing in the output would say so. This compares PyMuPDF's token stream with
poppler's `pdftotext` on the same files and reports agreement.

Agreement is multiset overlap: how many tokens the two engines agree on, divided
by the larger of the two counts. That is insensitive to reading-order
differences, which is what we want here — this checks extraction, not layout.
"""

from __future__ import annotations

import shutil
import statistics
import subprocess
from collections import Counter
from pathlib import Path

from .compare import TOKEN_RE


def tokens_pymupdf(pdf: Path) -> list[str]:
    import pymupdf

    doc = pymupdf.open(pdf)
    try:
        text = "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()
    return TOKEN_RE.findall(text)


def tokens_pdftotext(pdf: Path) -> list[str] | None:
    if not shutil.which("pdftotext"):
        return None
    try:
        out = subprocess.run(
            ["pdftotext", "-q", "-enc", "UTF-8", str(pdf), "-"],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    return TOKEN_RE.findall(out.stdout)


def agreement(a: list[str], b: list[str]) -> float:
    """Multiset overlap: shared tokens over the larger count."""
    if not a and not b:
        return 1.0
    ca, cb = Counter(a), Counter(b)
    shared = sum((ca & cb).values())
    largest = max(sum(ca.values()), sum(cb.values()))
    return shared / largest if largest else 1.0


def crosscheck(run_dir: Path, threshold: float = 0.99) -> tuple[list[dict], dict]:
    """Compare every PDF in a run.

    Per-document agreement is not the gate: text boxes and columns are read in
    different orders by different engines, and a low score can simply mean the
    document has no extractable text for one of them. The gate is the median,
    and the outliers are reported for review - they are findings, not noise.
    """
    pdfs = sorted(
        list(run_dir.glob("ref/*/*.pdf")) + list(run_dir.glob("cand/*/*.pdf"))
    )
    rows: list[dict] = []
    if not pdfs:
        return ([{"error": "no PDFs found in run"}], {"ok": False})

    if tokens_pdftotext(pdfs[0]) is None:
        return ([{"error": "pdftotext not available"}], {"ok": False})

    for pdf in pdfs:
        mine = tokens_pymupdf(pdf)
        theirs = tokens_pdftotext(pdf)
        if theirs is None:
            rows.append({"pdf": str(pdf), "agreement": 0.0, "status": "unreadable"})
            continue
        score = agreement(mine, theirs)
        rows.append(
            {
                "pdf": str(pdf.relative_to(run_dir)),
                "tokens_pymupdf": len(mine),
                "tokens_pdftotext": len(theirs),
                "agreement": round(score, 5),
                "status": "ok" if score >= threshold else "outlier",
            }
        )

    values = [r["agreement"] for r in rows if "agreement" in r]
    median = statistics.median(values) if values else 0.0
    outliers = [r for r in rows if r.get("status") != "ok"]
    summary = {
        "documents": len(rows),
        "median": round(median, 5),
        "min": round(min(values), 5) if values else 0.0,
        "outliers": len(outliers),
        "threshold": threshold,
        "ok": median >= threshold,
    }
    return rows, summary
