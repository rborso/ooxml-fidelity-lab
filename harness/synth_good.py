"""Candidate known-good documents.

These are built only from constructs that already measured clean: body text,
headings, emphasis, alignment, indentation, spacing, hyperlinks, tabs, breaks,
section breaks, content controls, simple fields and tracked insertions.

Deliberately excluded, because they are known to drift on the clean renderer:
tables (T2 geometry), bulleted and numbered lists (font substitution), text
boxes, content controls inside a shape, Georgia, and embedded objects. A
known-good control that already fails is worthless as a regression detector.

Nothing here is declared good. The pool is generated, measured, and only the
documents that actually score PASS are promoted. See promote-known-good.sh.
"""

from __future__ import annotations

from pathlib import Path

from . import synth

LOREM = synth.LOREM

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def para(
    text: str,
    *,
    align: str | None = None,
    indent: str | None = None,
    spacing: str | None = None,
    bold: bool = False,
    italic: bool = False,
    size: int | None = None,
    sup: bool = False,
    before: bool = False,
) -> str:
    ppr = ""
    if align:
        ppr += f'<w:jc w:val="{align}"/>'
    if indent:
        ppr += indent
    if spacing:
        ppr += spacing
    if before:
        ppr += '<w:pageBreakBefore/>'
    ppr = f"<w:pPr>{ppr}</w:pPr>" if ppr else ""

    rpr = ""
    if bold:
        rpr += "<w:b/>"
    if italic:
        rpr += "<w:i/>"
    if sup:
        rpr += '<w:vertAlign w:val="superscript"/>'
    if size:
        rpr += f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>'
    rpr = f"<w:rPr>{rpr}</w:rPr>" if rpr else ""
    return f'<w:p>{ppr}<w:r>{rpr}<w:t xml:space="preserve">{text}</w:t></w:r></w:p>'


def letter(seed: int) -> list[str]:
    return [
        para(f"Subject: case {seed} — reference material", bold=True, size=28),
        para(f"Dear Sir or Madam, {LOREM}."),
        para(f"This is paragraph two of the letter, variant {seed}. {LOREM}."),
        para(f"And a third paragraph closing the letter, variant {seed}. {LOREM}."),
        para("Yours faithfully,"),
        para("Department"),
    ]


def headings(seed: int) -> list[str]:
    return [
        para(f"Main heading {seed}", bold=True, size=36),
        para(f"Body under the main heading. {LOREM}."),
        para(f"Subheading {seed}", bold=True, size=28),
        para(f"Body under the subheading. {LOREM}."),
    ]


def emphasis(seed: int) -> list[str]:
    return [
        para(f"Plain text, then ", italic=True) + "",
        para(f"Bold statement {seed}.", bold=True),
        para(f"Italic remark {seed}.", italic=True),
        para(f"Body text at normal weight. {LOREM}."),
    ]


def alignment(seed: int) -> list[str]:
    return [
        para(f"Left aligned, variant {seed}. {LOREM}", align="left"),
        para(f"Centred line, variant {seed}.", align="center"),
        para(f"Right aligned, variant {seed}.", align="right"),
        para(f"Justified body text, variant {seed}. {LOREM} {LOREM}", align="both"),
    ]


def indentation(seed: int) -> list[str]:
    return [
        para(f"No indent, variant {seed}. {LOREM}"),
        para(
            f"Indented once, variant {seed}. {LOREM}",
            indent='<w:ind w:left="567"/>',
        ),
        para(
            f"Indented twice, variant {seed}. {LOREM}",
            indent='<w:ind w:left="1134"/>',
        ),
        para(
            f"First line indent, variant {seed}. {LOREM}",
            indent='<w:ind w:firstLine="425"/>',
        ),
    ]


def spacing(seed: int) -> list[str]:
    return [
        para(f"Single spaced, variant {seed}. {LOREM}", spacing='<w:spacing w:after="0" w:line="240" w:lineRule="auto"/>'),
        para(f"One and a half, variant {seed}. {LOREM}", spacing='<w:spacing w:after="120" w:line="360" w:lineRule="auto"/>'),
        para(f"Double spaced, variant {seed}. {LOREM}", spacing='<w:spacing w:after="0" w:line="480" w:lineRule="auto"/>'),
    ]


def hyperlinks(seed: int) -> list[str]:
    return [
        para(f"Before the link, variant {seed}."),
        '<w:p><w:hyperlink w:anchor="top"><w:r><w:t>jump to top</w:t></w:r></w:hyperlink></w:p>',
        para(f"After the link, variant {seed}. {LOREM}"),
    ]


def tabs_and_breaks(seed: int) -> list[str]:
    return [
        '<w:p><w:r><w:t>col A</w:t><w:tab/><w:t>col B</w:t><w:tab/><w:t>col C</w:t></w:r></w:p>',
        '<w:p><w:r><w:t>line one</w:t><w:br/><w:t>line two</w:t><w:br/><w:t>line three</w:t></w:r></w:p>',
        para(f"Trailing paragraph, variant {seed}."),
    ]


def superscript(seed: int) -> list[str]:
    return [
        '<w:p><w:r><w:t>H</w:t></w:r>'
        '<w:r><w:rPr><w:vertAlign w:val="subscript"/></w:rPr><w:t>2</w:t></w:r>'
        '<w:r><w:t>O, variant </w:t></w:r>'
        f'<w:r><w:t>{seed}</w:t></w:r></w:p>',
        '<w:p><w:r><w:t>E = mc</w:t></w:r>'
        '<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:t>2</w:t></w:r></w:p>',
    ]


def content_control(seed: int) -> list[str]:
    return [
        para(f"Before the control, variant {seed}."),
        '<w:sdt><w:sdtPr><w:alias w:val="field"/></w:sdtPr><w:sdtContent>'
        f"<w:p><w:r><w:t>controlled text {seed}</w:t></w:r></w:p></w:sdtContent></w:sdt>",
        para("After the control."),
    ]


def simple_field(seed: int) -> list[str]:
    return [
        para(f"Reference date, variant {seed}:"),
        '<w:p><w:fldSimple w:instr=" DATE \\@ &quot;dd-MM-yyyy&quot; ">'
        "<w:r><w:t>01-06-2025</w:t></w:r></w:fldSimple></w:p>",
        para("End of document."),
    ]


def tracked(seed: int) -> list[str]:
    return [
        para(f"Opening paragraph, variant {seed}."),
        '<w:p><w:ins w:id="1" w:author="reviewer" w:date="2025-06-01T09:00:00Z">'
        "<w:r><w:t>inserted sentence.</w:t></w:r></w:ins></w:p>",
        para("Closing paragraph."),
    ]


def section_break(seed: int) -> list[str]:
    return [
        para(f"First section, variant {seed}. {LOREM}"),
        '<w:p><w:pPr><w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr></w:pPr></w:p>',
        para(f"Second section, variant {seed}. {LOREM}"),
    ]


CONSTRUCTS = {
    "g-letter": letter,
    "g-headings": headings,
    "g-emphasis": emphasis,
    "g-alignment": alignment,
    "g-indentation": indentation,
    "g-spacing": spacing,
    "g-hyperlinks": hyperlinks,
    "g-tabs-breaks": tabs_and_breaks,
    "g-superscript": superscript,
    "g-content-control": content_control,
    "g-simple-field": simple_field,
    "g-tracked": tracked,
    "g-section-break": section_break,
}


def write(construct: str, seed: int, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    synth.write_body("".join(CONSTRUCTS[construct](seed)), path)
    return path


def write_all(out_dir: Path, variants: int = 5) -> list[Path]:
    paths = []
    for construct in CONSTRUCTS:
        for seed in range(1, variants + 1):
            paths.append(write(construct, seed, out_dir / f"{construct}-{seed}.docx"))
    return paths
