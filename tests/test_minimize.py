"""Minimiser tests. The render predicate is injected, so no Word is involved."""

from __future__ import annotations

import zipfile

import pytest

from harness import synth
from harness.minimize import ddmin, minimize_docx


def build_docx(path, paragraphs):
    body = "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs)
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
    return path


def body_paragraphs(path):
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml").decode()
    return xml.count("<w:p>")


def test_ddmin_keeps_only_the_needed_element():
    items = list(range(16))
    kept = ddmin(len(items), lambda keep: 7 in keep)
    assert kept == [7]


def test_ddmin_stops_when_nothing_can_be_removed():
    kept = ddmin(3, lambda keep: len(keep) >= 3)
    assert len(kept) == 3


def test_ddmin_reduces_body(tmp_path):
    source = build_docx(
        tmp_path / "full.docx",
        [f"para {i}" for i in range(16)],
    )
    # deliberately bury the needle in the middle
    build_docx(
        tmp_path / "full.docx",
        [f"para {i}" for i in range(7)] + ["needle here"] + [f"para {i}" for i in range(8, 16)],
    )
    assert body_paragraphs(source) == 16

    def predicate(candidate):
        with zipfile.ZipFile(candidate) as archive:
            return "needle" in archive.read("word/document.xml").decode()

    info = minimize_docx(source, tmp_path / "min.docx", predicate)
    assert info["elements_before"] == 16
    assert info["elements_after"] <= 2
    assert predicate(tmp_path / "min.docx")


def test_predicate_must_hold_on_the_source(tmp_path):
    source = build_docx(tmp_path / "a.docx", ["one", "two"])
    with pytest.raises(ValueError):
        minimize_docx(source, tmp_path / "b.docx", lambda _: False)


def test_sectpr_survives_minimisation(tmp_path):
    source = build_docx(tmp_path / "a.docx", ["one", "two", "three"])
    minimize_docx(tmp_path / "a.docx", tmp_path / "b.docx", lambda p: True)
    with zipfile.ZipFile(tmp_path / "b.docx") as archive:
        xml = archive.read("word/document.xml").decode()
    assert "<w:pgSz" in xml


def test_minimize_deep_reaches_inside_a_container(tmp_path):
    """A construct nested in a paragraph must be removable on its own."""
    body = ("<w:p><w:r><w:t>keep</w:t></w:r>"
            "<w:r><w:t>BURIED</w:t></w:r>"
            "<w:r><w:t>also keep</w:t></w:r></w:p>"
            "<w:p><w:r><w:t>noise</w:t></w:r></w:p>")
    source = build_docx(tmp_path / "deep.docx", [])
    # rebuild with the custom body
    with zipfile.ZipFile(source) as archive:
        entries = {n: archive.read(n) for n in archive.namelist()}
    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                f"<w:document {synth.NS}><w:body>{body}{synth.SECT}</w:body></w:document>")
    entries["word/document.xml"] = document.encode()
    with zipfile.ZipFile(source, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)

    def predicate(candidate):
        with zipfile.ZipFile(candidate) as archive:
            return "BURIED" in archive.read("word/document.xml").decode()

    from harness.minimize import minimize_deep
    info = minimize_deep(source, tmp_path / "deep.min.docx", predicate, 200)
    assert predicate(tmp_path / "deep.min.docx")
    assert info["elements_after"] < info["elements_before"]
    with zipfile.ZipFile(tmp_path / "deep.min.docx") as archive:
        xml = archive.read("word/document.xml").decode()
    assert "noise" not in xml


def test_document_text_joins_runs(tmp_path):
    """A token split across runs must still be found by the predicate."""
    source = build_docx(tmp_path / "split.docx", [])
    with zipfile.ZipFile(source) as archive:
        entries = {n: archive.read(n) for n in archive.namelist()}
    body = "<w:p><w:r><w:t>Hel</w:t></w:r><w:r><w:t>lo</w:t></w:r></w:p>"
    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                f"<w:document {synth.NS}><w:body>{body}{synth.SECT}</w:body></w:document>")
    entries["word/document.xml"] = document.encode()
    with zipfile.ZipFile(source, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    from harness.minimize import document_text
    assert document_text(source) == "Hello"
