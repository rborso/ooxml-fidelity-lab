"""Generate minimal single-construct DOCX files.

Dependency-free: a DOCX is a zip of XML. But "minimal" must not mean
"degenerate" — a document without document defaults and without an explicit
page size lets each engine invent its own, and every comparison then measures
defaults rather than the construct under test. These files therefore carry a
styles part with Word's defaults and an explicit A4 section.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
</Types>"""

PACKAGE_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

DOCUMENT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>
</Relationships>"""

# Minimal list definitions: decimal and bullet, so numbering is a real construct
# rather than an attribute pointing at nothing.
NUMBERING = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:abstractNum w:abstractNumId="0"><w:multiLevelType w:val="singleLevel"/>
<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/>
<w:lvlText w:val="%1."/><w:lvlJc w:val="left"/></w:lvl></w:abstractNum>
<w:abstractNum w:abstractNumId="1"><w:multiLevelType w:val="singleLevel"/>
<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/>
<w:lvlText w:val="&#x2022;"/><w:lvlJc w:val="left"/></w:lvl></w:abstractNum>
<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>
<w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num>
</w:numbering>"""

# Word's own defaults: Calibri 11pt, 8pt space after, 1.08 line spacing.
STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults>
<w:rPrDefault><w:rPr>
<w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="Calibri" w:cs="Calibri"/>
<w:sz w:val="22"/><w:szCs w:val="22"/>
<w:lang w:val="en-GB"/>
</w:rPr></w:rPrDefault>
<w:pPrDefault><w:pPr><w:spacing w:after="160" w:line="259" w:lineRule="auto"/></w:pPr></w:pPrDefault>
</w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>
</w:styles>"""

# Explicit A4, 1 inch margins. Without this Word defaults to Letter and
# LibreOffice to A4, and every line break then differs for the wrong reason.
SECT = """<w:sectPr>
<w:pgSz w:w="11906" w:h="16838"/>
<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/>
</w:sectPr>"""

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
    return f'<w:p><w:r>{rpr}<w:t xml:space="preserve">{text}</w:t></w:r></w:p>'


def _table(rows: list[list[str]]) -> str:
    grid = "".join('<w:gridCol w:w="2400"/>' for _ in rows[0])
    body = ""
    for row in rows:
        cells = "".join(
            f'<w:tc><w:tcPr><w:tcW w:w="2400" w:type="dxa"/></w:tcPr>'
            f"<w:p><w:r><w:t>{c}</w:t></w:r></w:p></w:tc>"
            for c in row
        )
        body += f"<w:tr>{cells}</w:tr>"
    return (
        '<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/>'
        "<w:tblBorders>"
        '<w:top w:val="single"/><w:left w:val="single"/>'
        '<w:bottom w:val="single"/><w:right w:val="single"/>'
        '<w:insideH w:val="single"/><w:insideV w:val="single"/>'
        "</w:tblBorders></w:tblPr>"
        f"<w:tblGrid>{grid}</w:tblGrid>{body}</w:tbl>"
    )


def _numbered(text: str, num_id: int = 1) -> str:
    return (
        f'<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="{num_id}"/></w:numPr></w:pPr>'
        f"<w:r><w:t>{text}</w:t></w:r></w:p>"
    )


def _sdt(text: str) -> str:
    return (
        f'<w:sdt><w:sdtPr><w:alias w:val="control"/></w:sdtPr><w:sdtContent>'
        f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:sdtContent></w:sdt>"
    )


def _textbox(text: str) -> str:
    # A bare w:txbxContent inside w:pict is not a valid shape and Word refuses
    # to open the file. Wrap it in a real VML shape.
    return (
        '<w:p><w:r><w:pict xmlns:v="urn:schemas-microsoft-com:vml">'
        '<v:shape id="labsdtb1" style="width:200pt;height:60pt" filled="f" stroked="f">'
        "<v:textbox><w:txbxContent>"
        f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"
        "</w:txbxContent></v:textbox></v:shape></w:pict></w:r></w:p>"
    )


def _field_date() -> str:
    return (
        '<w:p><w:fldSimple w:instr=" DATE \\@ &quot;yyyy-MM-dd&quot; ">'
        "<w:r><w:t>2026-01-01</w:t></w:r></w:fldSimple></w:p>"
    )


def _tracked(text: str) -> str:
    return (
        '<w:p><w:ins w:id="1" w:author="lab" w:date="2026-01-01T00:00:00Z">'
        f"<w:r><w:t>{text}</w:t></w:r></w:ins></w:p>"
    )


def _section_break() -> str:
    return '<w:p><w:pPr><w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr></w:pPr></w:p>'


def _merged_cells() -> str:
    return (
        '<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/></w:tblPr>'
        '<w:tblGrid><w:gridCol w:w="2400"/><w:gridCol w:w="2400"/></w:tblGrid>'
        '<w:tr><w:tc><w:tcPr><w:gridSpan w:val="2"/></w:tcPr>'
        "<w:p><w:r><w:t>spans both columns</w:t></w:r></w:p></w:tc></w:tr>"
        "<w:tr><w:tc><w:p><w:r><w:t>left</w:t></w:r></w:p></w:tc>"
        "<w:tc><w:p><w:r><w:t>right</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"
    )


def _nested_table() -> str:
    inner = (
        '<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/></w:tblPr>'
        '<w:tblGrid><w:gridCol w:w="1200"/></w:tblGrid>'
        "<w:tr><w:tc><w:p><w:r><w:t>inner</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"
    )
    return (
        '<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/></w:tblPr>'
        '<w:tblGrid><w:gridCol w:w="4800"/></w:tblGrid>'
        f"<w:tr><w:tc>{inner}<w:p/></w:tc></w:tr></w:tbl>"
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
    "merged-cells": [_para("Table with a spanned cell."), _merged_cells()],
    "nested-table": [_para("Table inside a table."), _nested_table()],
    "numbered-list": [_para("A numbered list:")] + [
        _numbered(f"item {i}") for i in range(1, 6)
    ],
    "bullet-list": [_para("A bulleted list:")] + [
        _numbered(f"point {i}", num_id=2) for i in range(1, 6)
    ],
    "hyperlink": [
        _para("Before the link."),
        '<w:p><w:hyperlink w:anchor="top"><w:r><w:t>jump to top</w:t></w:r></w:hyperlink></w:p>',
        _para("After the link."),
    ],
    "textbox": [_para("Before the box."), _textbox("inside a text box"), _para("After the box.")],
    "content-control": [_para("Before the control."), _sdt("inside a content control")],
    "field-date": [_para("A date field:"), _field_date()],
    "track-changes": [_para("Before the revision."), _tracked("inserted by a reviewer")],
    "section-break": [_para("First section."), _section_break(), _para("Second section.")],
    "tabs-breaks": [
        '<w:p><w:r><w:t>before</w:t><w:tab/><w:t>after tab</w:t>'
        "<w:br/><w:t>after break</w:t></w:r></w:p>"
    ],
    "superscript": [
        '<w:p><w:r><w:t>E = mc</w:t></w:r><w:r><w:rPr><w:vertAlign w:val="superscript"/>'
        "</w:rPr><w:t>2</w:t></w:r></w:p>"
    ],
}


def build(construct: str) -> str:
    if construct not in CONSTRUCTS:
        raise KeyError(f"unknown construct {construct!r}; known: {sorted(CONSTRUCTS)}")
    body = "".join(CONSTRUCTS[construct])
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<w:document {NS}><w:body>{body}{SECT}</w:body></w:document>"
    )


def write_body(body: str, path: Path) -> Path:
    """Write a document from raw body XML. Shared by the construct sets."""
    path.parent.mkdir(parents=True, exist_ok=True)
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<w:document {NS}><w:body>{body}{SECT}</w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", PACKAGE_RELS)
        z.writestr("word/document.xml", document)
        z.writestr("word/_rels/document.xml.rels", DOCUMENT_RELS)
        z.writestr("word/styles.xml", STYLES)
        z.writestr("word/numbering.xml", NUMBERING)
    return path


def write(construct: str, path: Path) -> Path:
    return write_body("".join(CONSTRUCTS[construct]), path)


def write_all(out_dir: Path) -> list[Path]:
    return [write(name, out_dir / f"{name}.docx") for name in CONSTRUCTS]
