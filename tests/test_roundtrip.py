"""Round-trip tests. Only the file-level parts run here; conversion needs podman."""

from __future__ import annotations

import zipfile

import pytest

from harness import synth
from harness.roundtrip import mutate, normalize, signature, text_of


def build(tmp_path, paragraphs=("one", "two")):
    path = tmp_path / "doc.docx"
    synth.write("plain", path)
    return path


def test_normalize_removes_rsids():
    xml = b'<w:p w:rsidR="00AB" w:rsidRDefault="00CD"><w:t>x</w:t></w:p>'
    assert b"rsid" not in normalize(xml)


def test_signature_ignores_rsid_changes(tmp_path):
    a = tmp_path / "a.docx"
    synth.write("plain", a)

    b = tmp_path / "b.docx"
    with zipfile.ZipFile(a) as archive:
        entries = {n: archive.read(n) for n in archive.namelist()}
    document = entries["word/document.xml"].decode()
    document = document.replace("<w:p>", '<w:p w:rsidR="00FF00">', 1)
    entries["word/document.xml"] = document.encode()
    with zipfile.ZipFile(b, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)

    assert signature(a) == signature(b)


def test_mutation_is_deterministic(tmp_path):
    source = tmp_path / "src.docx"
    synth.write("plain", source)
    first = mutate(source, tmp_path / "m1.docx", seed=7)
    second = mutate(source, tmp_path / "m2.docx", seed=7)
    assert signature(first) == signature(second)


def test_mutation_adds_text(tmp_path):
    source = tmp_path / "src.docx"
    synth.write("plain", source)
    edited = mutate(source, tmp_path / "m.docx", seed=3)
    assert "lab edit 3" in text_of(edited)
    assert "lab edit 3" not in text_of(source)


def test_different_seeds_differ(tmp_path):
    source = tmp_path / "src.docx"
    synth.write("plain", source)
    assert text_of(mutate(source, tmp_path / "a.docx", 1)) != text_of(
        mutate(source, tmp_path / "b.docx", 2)
    )
