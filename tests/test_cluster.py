"""Clustering tests: signatures must be stable and discriminating."""

from __future__ import annotations

import zipfile

from harness import synth
from harness.cluster import cluster, describe, signature_hash, construct_signature


def build_docx(path, body):
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


PARA = "<w:p><w:r><w:t>hello</w:t></w:r></w:p>"
TABLE = (
    "<w:tbl><w:tblPr/><w:tblGrid><w:gridCol w:w='100'/></w:tblGrid>"
    "<w:tr><w:tc><w:p><w:r><w:t>c</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"
)
TEXTBOX = (
    "<w:p><w:r><w:pict><w:txbxContent>"
    "<w:p><w:r><w:t>box</w:t></w:r></w:p>"
    "</w:txbxContent></w:pict></w:r></w:p>"
)


def test_signature_is_stable(tmp_path):
    doc = build_docx(tmp_path / "a.docx", PARA + TABLE)
    assert signature_hash(construct_signature(doc)) == signature_hash(construct_signature(doc))


def test_signature_discriminates(tmp_path):
    plain = build_docx(tmp_path / "plain.docx", PARA)
    with_table = build_docx(tmp_path / "table.docx", PARA + TABLE)
    assert signature_hash(construct_signature(plain)) != signature_hash(
        construct_signature(with_table)
    )


def test_signature_counts_constructs(tmp_path):
    doc = build_docx(tmp_path / "t.docx", PARA + TEXTBOX)
    counts = construct_signature(doc)
    assert counts.get("txbxContent") == 1
    assert counts.get("tbl") is None


def test_cluster_groups_same_constructs(tmp_path):
    a = build_docx(tmp_path / "a.docx", PARA + TABLE)
    b = build_docx(tmp_path / "b.docx", PARA + TABLE)
    c = build_docx(tmp_path / "c.docx", PARA + TEXTBOX)
    groups = cluster([("a", a, "T0"), ("b", b, "T0"), ("c", c, "T0")])
    assert groups[0]["size"] == 2
    assert set(groups[0]["documents"]) == {"a", "b"}
    assert groups[1]["size"] == 1


def test_describe_is_readable(tmp_path):
    doc = build_docx(tmp_path / "d.docx", PARA + TABLE + TABLE)
    text = describe(construct_signature(doc))
    assert "tblx2" in text
