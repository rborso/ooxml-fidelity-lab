"""Generate minimal single-construct DOCX files.

Deliberately dependency-free: a DOCX is a zip of XML, and constructing it by
hand keeps the generated document exactly as small as the construct under test.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

NS = (
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
)

LOREM = (
    "the quick brown fox jumps over the lazy dog and then keeps running "
    "through the quiet fields until it reaches the river bank"
)


def _para(text: str, *, font: str | None = None, bold: bool = False, size: int | None = None) -> str:
    rpr = ""
    if font:
        rpr += f'<w:rFonts w:ascii="{font}" w:hAnsi="{font}" w:cs="{font}"/>'
    if bold:
        rpr += "<w:b/>"
    if size:
        rpr += f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>'
    rpr = f"<w:rPr>{rpr}</w:rPr>" if rpr else ""
    return f"<w:p><w:r>{rpr}<w:t xml:space=\"preserve\">{text}</w:t></w:r></w:p>"


def _table(rows: list[list[str]]) -> str:
    grid = "".join("<w:gridCol w:w=\"2400\"/>" for _ in rows[0])
    body = ""
    for row in rows:
        cells = "".join(
            f'<w:tc><w:tcPr><w:tcW w:w="2400" w:type="dxa"/></w:tcPr>'
            f"<w:p><w:r><w:t>{c}</w:t></w:r></w:p></w:tc>"
            for c in row
        )
        body += f"<w:tr>{cells}</w:tr>"
    return (
        "<w:tbl><w:tblPr><w:tblW w:w=\"0\" w:type=\"auto\"/>"
        "<w:tblBorders>"
        "<w:top w:val=\"single\"/><w:left w:val=\"single\"/>"
        "<w:bottom w:val=\"single\"/><w:right w:val=\"single\"/>"
        "<w:insideH w:val=\"single\"/><w:insideV w:val=\"single\"/>"
        "</w:tblBorders></w:tblPr>"
        f"<w:tblGrid>{grid}</w:tblGrid>{body}</w:tbl>"
    )


CONSTRUCTS: dict[str, list[str]] = {
    "plain": [_para(f"Line {i}: {LOREM}.") for i in range(1, 16)],
    "georgia": [
        _para("Default body text in the theme font."),
        _para(f"Georgia paragraph: {LOREM}.", font="Georgia"),
    ],
    "bold-size": [
        _para("A heading", bold=True, size=36),
        _para(f"Body under the heading: {LOREM}."),
    ],
    "table": [
        _para("A document with a table."),
        _table([["Year", "Count", "Notes"], ["2024", "12", "alpha"], ["2025", "31", "beta"]]),
        _para("Text after the table."),
    ],
}


def build(construct: str) -> bytes:
    if construct not in CONSTRUCTS:
        raise KeyError(f"unknown construct {construct!r}; known: {sorted(CONSTRUCTS)}")
    body = "".join(CONSTRUCTS[construct])
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<w:document {NS}><w:body>{body}<w:sectPr/></w:body></w:document>"
    )
    return document.encode()


def write(construct: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = build(construct)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/document.xml", document)
    return path


def write_all(out_dir: Path) -> list[Path]:
    return [write(name, out_dir / f"{name}.docx") for name in CONSTRUCTS]
