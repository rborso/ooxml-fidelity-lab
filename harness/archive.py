"""Archival checks on the rendered PDF.

If a document is going to be the record of a decision, the PDF has to stand on
its own: text you can select, fonts that travel with it, page count that does
not depend on the machine reading it.
"""

from __future__ import annotations

from pathlib import Path


def check_pdf(pdf: Path, expect_pages: int | None = None) -> dict:
    import pymupdf

    issues: list[str] = []
    doc = pymupdf.open(pdf)
    try:
        page_count = doc.page_count
        if page_count == 0:
            issues.append("no pages")

        fonts: set[str] = set()
        unembedded: set[str] = set()
        for page in doc:
            for font in page.get_fonts():
                # (xref, ext, type, basefont, name, encoding)
                name = font[3] or "unknown"
                fonts.add(name)
                if not font[1]:
                    unembedded.add(name)

        tokens = 0
        for page in doc:
            tokens += len(page.get_text().split())

        if tokens == 0:
            issues.append("no extractable text")
        if unembedded:
            issues.append("unembedded fonts: " + ", ".join(sorted(unembedded)[:5]))
        if expect_pages is not None and page_count != expect_pages:
            issues.append(f"page count {page_count} != {expect_pages}")

        return {
            "pdf": str(pdf),
            "pages": page_count,
            "tokens": tokens,
            "fonts": sorted(fonts),
            "unembedded_fonts": sorted(unembedded),
            "issues": issues,
            "pass": not issues,
        }
    finally:
        doc.close()


def check_run(run_dir: Path) -> tuple[list[dict], bool]:
    pdfs = sorted(run_dir.glob("cand/*/*.pdf")) + sorted(run_dir.glob("ref/*/*.pdf"))
    results = [check_pdf(pdf) for pdf in pdfs]
    return results, all(r["pass"] for r in results)
