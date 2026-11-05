"""Archival checks: a PDF that cannot be read or does not carry its fonts is not
a record."""

from __future__ import annotations

from harness.archive import check_pdf


def make_pdf(path, text="hello archive", pages=1):
    import pymupdf

    doc = pymupdf.open()
    for index in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"{text} {index}")
    doc.save(path)
    doc.close()
    return path


def test_text_pdf_passes(tmp_path):
    result = check_pdf(make_pdf(tmp_path / "ok.pdf"))
    assert result["pass"]
    assert result["tokens"] > 0
    assert result["pages"] == 1


def test_empty_page_has_no_text(tmp_path):
    import pymupdf

    doc = pymupdf.open()
    doc.new_page()
    path = tmp_path / "blank.pdf"
    doc.save(path)
    doc.close()

    result = check_pdf(path)
    assert not result["pass"]
    assert any("no extractable text" in issue for issue in result["issues"])


def test_page_count_mismatch_is_reported(tmp_path):
    result = check_pdf(make_pdf(tmp_path / "two.pdf", pages=2), expect_pages=3)
    assert not result["pass"]
    assert any("page count" in issue for issue in result["issues"])


def test_fonts_are_listed(tmp_path):
    result = check_pdf(make_pdf(tmp_path / "f.pdf"))
    assert result["fonts"]
