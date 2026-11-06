"""Body-extraction tests: splitting a document must be surgical."""

from __future__ import annotations

import zipfile

import pytest

from harness import synth
from harness.split import extract

PARA = "<w:p><w:r><w:t>plain</w:t></w:r></w:p>"
TEXTBOX = (
    "<w:p><w:r><w:pict><w:txbxContent>"
    "<w:p><w:r><w:t>boxed</w:t></w:r></w:p>"
    "</w:txbxContent></w:pict></w:r></w:p>"
)


def build(tmp_path, body):
    path = tmp_path / "doc.docx"
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<w:document {synth.NS}><w:body>{body}{synth.SECT}</w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", synth.CONTENT_TYPES)
        archive.writestr("_rels/.rels", synth.PACKAGE_RELS)
        archive.writestr("word/document.xml", document)
        archive.writestr("word/_rels/document.xml.rels", synth.DOCUMENT_RELS)
        archive.writestr("word/styles.xml", synth.STYLES)
        archive.writestr("word/numbering.xml", synth.NUMBERING)
    return path


def body_xml(path):
    with zipfile.ZipFile(path) as archive:
        return archive.read("word/document.xml").decode()


def test_keeps_only_matching_body_children(tmp_path):
    source = build(tmp_path, PARA + TEXTBOX)
    out = tmp_path / "out.docx"
    info = extract(source, out, ["txbxContent"])
    xml = body_xml(out)
    assert "boxed" in xml
    assert "plain" not in xml
    assert info["kept"] == 1 and info["removed"] == 1


TABLE = (
    "<w:tbl><w:tblPr/><w:tblGrid><w:gridCol w:w='100'/></w:tblGrid>"
    "<w:tr><w:tc><w:p><w:r><w:t>cell</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"
)


def test_adjacent_tables_are_separated(tmp_path):
    """Word merges adjacent tables; an empty paragraph keeps them apart."""
    source = build(tmp_path, TABLE + TABLE + TABLE)
    out = tmp_path / "out.docx"
    extract(source, out, ["cell"])
    xml = body_xml(out)
    assert xml.count("<w:tbl>") == 3
    assert xml.count("<w:p/>") == 2


def test_trailing_page_break_is_removed(tmp_path):
    """A break with nothing after it only produces a blank page."""
    with_break = (
        '<w:p><w:r><w:t>kept</w:t></w:r><w:r><w:br w:type="page"/></w:r></w:p>'
    )
    source = build(tmp_path, with_break + PARA)
    out = tmp_path / "out.docx"
    info = extract(source, out, ["kept"])
    xml = body_xml(out)
    assert 'w:type="page"' not in xml
    assert info["page_breaks_removed"] == 1


def test_page_break_with_content_after_it_is_kept(tmp_path):
    """The break lives in a retained paragraph; content follows it."""
    first = '<w:p><w:r><w:t>kept</w:t></w:r><w:r><w:br w:type="page"/></w:r></w:p>'
    second = '<w:p><w:r><w:t>kept again</w:t></w:r></w:p>'
    source = build(tmp_path, first + second)
    out = tmp_path / "out.docx"
    extract(source, out, ["kept"])
    assert 'w:type="page"' in body_xml(out)


def test_section_properties_are_preserved(tmp_path):
    source = build(tmp_path, PARA + TEXTBOX)
    out = tmp_path / "out.docx"
    extract(source, out, ["txbxContent"])
    assert "<w:pgSz" in body_xml(out)


def test_all_mode_requires_every_needle(tmp_path):
    source = build(tmp_path, PARA + TEXTBOX)
    out = tmp_path / "out.docx"
    extract(source, out, ["txbxContent", "not-present"], mode="all")
    xml = body_xml(out)
    assert "boxed" not in xml


def test_any_mode_matches_one_needle(tmp_path):
    source = build(tmp_path, PARA + TEXTBOX)
    out = tmp_path / "out.docx"
    extract(source, out, ["txbxContent", "not-present"], mode="any")
    assert "boxed" in body_xml(out)


def test_output_is_a_readable_package(tmp_path):
    source = build(tmp_path, PARA + TEXTBOX)
    out = tmp_path / "out.docx"
    extract(source, out, ["plain"])
    with zipfile.ZipFile(out) as archive:
        names = archive.namelist()
    for part in ("word/document.xml", "word/styles.xml", "[Content_Types].xml"):
        assert part in names
