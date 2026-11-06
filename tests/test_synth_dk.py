"""Denmark reconstructions must be valid packages and carry their symptom."""

from __future__ import annotations

import zipfile

from lxml import etree

from harness import synth_dk

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def test_six_constructs():
    assert len(synth_dk.CONSTRUCTS) == 6


def test_every_construct_has_a_reported_symptom():
    for construct in synth_dk.CONSTRUCTS:
        assert construct in synth_dk.SYMPTOMS
        assert synth_dk.SYMPTOMS[construct]


def test_every_construct_builds_a_valid_package(tmp_path):
    for construct in synth_dk.CONSTRUCTS:
        path = synth_dk.write(construct, 1, tmp_path / f"{construct}.docx")
        with zipfile.ZipFile(path) as archive:
            document = archive.read("word/document.xml")
        tree = etree.fromstring(document)
        body = tree.find(f"{W}body")
        assert body is not None and len(body) > 0


def test_georgia_construct_actually_requests_georgia(tmp_path):
    path = synth_dk.write("dk-georgia-template", 1, tmp_path / "g.docx")
    with zipfile.ZipFile(path) as archive:
        document = archive.read("word/document.xml").decode()
    assert 'w:ascii="Georgia"' in document


def test_tracked_changes_construct_has_revisions(tmp_path):
    path = synth_dk.write("dk-tracked-changes-heavy", 1, tmp_path / "t.docx")
    with zipfile.ZipFile(path) as archive:
        document = archive.read("word/document.xml").decode()
    assert "<w:ins " in document
    assert "<w:del " in document
    assert "delText" in document


def test_cross_agency_construct_has_sdt_inside_textbox(tmp_path):
    path = synth_dk.write("dk-cross-agency-blank", 1, tmp_path / "c.docx")
    with zipfile.ZipFile(path) as archive:
        document = archive.read("word/document.xml").decode()
    box = document.split("<w:txbxContent>")[1]
    assert "<w:sdt>" in box


def test_variants_differ(tmp_path):
    a = synth_dk.write("dk-ministry-form", 1, tmp_path / "a.docx")
    b = synth_dk.write("dk-ministry-form", 2, tmp_path / "b.docx")
    assert a.read_bytes() != b.read_bytes()
