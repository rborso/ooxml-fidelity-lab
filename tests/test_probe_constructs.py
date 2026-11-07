"""Probe and construct index: the two questions that precede any patch."""

from __future__ import annotations

import zipfile
from pathlib import Path

from harness import constructs, probe

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
V = "urn:schemas-microsoft-com:vml"


def _docx(path: Path, body: str) -> Path:
    xml = (f'<w:document xmlns:w="{W}" xmlns:v="{V}"><w:body>{body}</w:body></w:document>')
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", xml)
    return path


def test_verdict_names_the_stage():
    def stages(txt, odt, docx):
        return {"txt": {"found": txt}, "odt": {"found": odt}, "docx": {"found": docx}}

    assert probe.verdict(stages(False, False, False)) == "import"
    assert probe.verdict(stages(True, False, False)) == "import-to-native"
    assert probe.verdict(stages(True, True, False)) == "round-trip"
    assert probe.verdict(stages(True, True, True)) == "later-stage"


def test_probe_rejects_a_missing_binary(tmp_path: Path):
    doc = _docx(tmp_path / "a.docx", "<w:p/>")
    try:
        probe.probe(doc, "x", str(tmp_path / "nope"))
    except probe.ProbeError as exc:
        assert "binary" in str(exc)
    else:
        raise AssertionError("expected ProbeError")


def test_construct_signature_finds_nested_sdt(tmp_path: Path):
    body = ("<w:p><w:pict><v:textbox><w:txbxContent>"
            "<w:sdt><w:sdtPr/><w:sdtContent><w:p/></w:sdtContent></w:sdt>"
            "</w:txbxContent></v:textbox></w:pict></w:p>")
    sig = constructs.signature(_docx(tmp_path / "sdt.docx", body))
    assert sig["counts"]["sdt"] == 1
    assert sig["counts"]["txbxContent"] == 1
    assert any("txbxContent" in path and "sdt" in path for path in sig["paths"])


def test_construct_signature_without_sdt(tmp_path: Path):
    sig = constructs.signature(_docx(tmp_path / "plain.docx", "<w:p><w:r/></w:p>"))
    assert sig["counts"].get("sdt", 0) == 0


def test_query_matches_all_terms(tmp_path: Path):
    weird = _docx(tmp_path / "weird.docx",
                  "<w:p><w:pict><v:textbox><w:txbxContent><w:sdt/></w:txbxContent>"
                  "</v:textbox></w:pict></w:p>")
    plain = _docx(tmp_path / "plain.docx", "<w:p><w:tbl><w:tr/></w:tbl></w:p>")
    out = tmp_path / "index.json"
    index = constructs.build([weird, plain], out)

    assert constructs.query(index, "txbxContent sdt") == ["weird"]
    assert constructs.query(index, "tbl") == ["plain"]
    assert constructs.query(index, "sdt tbl") == []
    assert constructs.load(out)["weird"]["counts"]["sdt"] == 1


def test_build_records_unreadable_documents(tmp_path: Path):
    broken = tmp_path / "broken.docx"
    broken.write_bytes(b"not a zip")
    index = constructs.build([broken], tmp_path / "i.json")
    assert "error" in index["broken"]
    assert constructs.query(index, "sdt") == []
