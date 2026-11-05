"""Synthetic construct tests: every construct must be a valid package."""

from __future__ import annotations

import zipfile

from lxml import etree

from harness import synth

REQUIRED_PARTS = [
    "[Content_Types].xml",
    "_rels/.rels",
    "word/document.xml",
    "word/_rels/document.xml.rels",
    "word/styles.xml",
    "word/numbering.xml",
]


def test_at_least_twelve_constructs():
    assert len(synth.CONSTRUCTS) >= 12


def test_every_construct_builds_a_valid_package(tmp_path):
    for name in synth.CONSTRUCTS:
        path = synth.write(name, tmp_path / f"{name}.docx")
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            for part in REQUIRED_PARTS:
                assert part in names, f"{name} missing {part}"
            document = archive.read("word/document.xml")
        tree = etree.fromstring(document)
        assert tree.tag.endswith("}document"), name
        body = tree.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}body")
        assert body is not None and len(body) > 0, f"{name} has an empty body"


def test_constructs_are_distinct():
    """Two constructs must not produce byte-identical bodies."""
    documents = {name: synth.build(name) for name in synth.CONSTRUCTS}
    assert len(set(documents.values())) == len(documents)


def test_numbering_part_defines_the_ids_used():
    xml = synth.NUMBERING
    assert 'w:numId="1"' in xml
    assert 'w:numId="2"' in xml


def test_unknown_construct_raises():
    import pytest

    with pytest.raises(KeyError):
        synth.build("does-not-exist")
