"""Candidate known-good documents must be valid packages."""

from __future__ import annotations

import zipfile

from lxml import etree

from harness import synth_good

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def test_thirteen_families():
    assert len(synth_good.CONSTRUCTS) >= 13


def test_generates_at_least_forty():
    assert len(synth_good.CONSTRUCTS) * 5 >= 40


def test_every_family_builds_a_valid_package(tmp_path):
    for construct in synth_good.CONSTRUCTS:
        path = synth_good.write(construct, 1, tmp_path / f"{construct}.docx")
        with zipfile.ZipFile(path) as archive:
            document = archive.read("word/document.xml")
        tree = etree.fromstring(document)
        body = tree.find(f"{W}body")
        assert body is not None and len(body) > 0, construct


def test_no_tables_or_lists_by_design(tmp_path):
    """Tables and lists already drift on the clean renderer, so including them
    would produce controls that fail before any patch exists."""
    for construct in synth_good.CONSTRUCTS:
        path = synth_good.write(construct, 1, tmp_path / f"{construct}.docx")
        with zipfile.ZipFile(path) as archive:
            document = archive.read("word/document.xml").decode()
        assert "<w:tbl>" not in document, construct
        assert "w:numPr" not in document, construct


def test_variants_differ(tmp_path):
    a = synth_good.write("g-letter", 1, tmp_path / "a.docx")
    b = synth_good.write("g-letter", 2, tmp_path / "b.docx")
    assert a.read_bytes() != b.read_bytes()
