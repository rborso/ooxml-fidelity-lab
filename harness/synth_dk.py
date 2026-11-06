"""Documents mirroring the failure classes reported from Denmark's pilot.

The Ministry of Digitization's pilot documents were never published, so these
are not the originals. Each construct reconstructs one *reported symptom* from
the contemporaneous Danish reporting (Ingeniøren, December 2025) and the
ministry's own description of the test criteria:

  - documents from other agencies opening blank
  - tracked changes that were difficult to accept
  - odd line spacing when pasting text
  - a template styled in Georgia, which the container does not ship
  - ministry templates with tables and fields

Treat them as reproductions of the reported behaviour, not as a corpus of
Danish government documents. Any finding here is evidence about the *construct*,
never about the original file.
"""

from __future__ import annotations

from pathlib import Path

from . import synth

LOREM = synth.LOREM


def _p(text: str, **kwargs) -> str:
    return synth._para(text, **kwargs)


def _variant(seed: int, base: str) -> str:
    return f"{base} (variant {seed})"


def georgia_template(seed: int) -> list[str]:
    """Reported: the template was styled in Georgia; the container has no
    metric-compatible Georgia, so substitution moved every line break."""
    return [
        _p(_variant(seed, "MINISTRY LETTERHEAD"), bold=True, size=32, font="Georgia"),
        _p("Case number: 2025-0000", font="Georgia"),
        _p(
            f"Dear Sir or Madam, {LOREM}. " * 2,
            font="Georgia",
        ),
        _p("Yours faithfully,", font="Georgia"),
        _p("Department for Digitalisation", font="Georgia"),
    ]


def tracked_changes_heavy(seed: int) -> list[str]:
    """Reported: track changes was difficult to work with. Many revisions in
    one paragraph, including deletions and formatting changes."""
    runs = []
    for index in range(1, 7):
        author = f"author{index}"
        runs.append(
            f'<w:ins w:id="{index}" w:author="{author}" w:date="2025-06-0{index}T09:00:00Z">'
            f"<w:r><w:t>inserted text {index} </w:t></w:r></w:ins>"
        )
        runs.append(
            f'<w:del w:id="{100 + index}" w:author="{author}" w:date="2025-06-0{index}T09:05:00Z">'
            f'<w:r><w:delText>deleted text {index} </w:delText></w:r></w:del>'
        )
    return [
        _p(_variant(seed, "A heavily revised case note.")),
        "<w:p>" + "".join(runs) + "</w:p>",
        _p(f"Closing paragraph. {LOREM}."),
    ]


def line_spacing_mixed(seed: int) -> list[str]:
    """Reported: odd line spacing appeared when text was pasted in. Different
    line rules and spacing values in adjacent paragraphs."""
    rules = [
        ('w:line="240" w:lineRule="auto"', 'w:after="0"'),
        ('w:line="259" w:lineRule="auto"', 'w:after="160"'),
        ('w:line="360" w:lineRule="exact"', 'w:after="0"'),
        ('w:line="276" w:lineRule="atLeast"', 'w:after="80"'),
    ]
    body = []
    for index, (line, after) in enumerate(rules, start=1):
        body.append(
            f'<w:p><w:pPr><w:spacing {line} {after}/></w:pPr>'
            f"<w:r><w:t>{_variant(seed, f'paragraph {index}')} {LOREM}</w:t></w:r></w:p>"
        )
    return body


def cross_agency_blank(seed: int) -> list[str]:
    """Reported: documents received from other agencies opened blank. That is
    the content-control-inside-a-text-box shape, which the importer skips."""
    return [
        _p(_variant(seed, "Cover page.")),
        '<w:p><w:r><w:pict xmlns:v="urn:schemas-microsoft-com:vml">'
        '<v:shape id="dkbox" style="width:400pt;height:120pt" filled="f" stroked="f">'
        "<v:textbox><w:txbxContent>"
        '<w:sdt><w:sdtPr><w:alias w:val="agency"/></w:sdtPr><w:sdtContent>'
        f"<w:p><w:r><w:t>Agency reply text {seed}: CME Offshore 09 Accounting</w:t></w:r></w:p>"
        "</w:sdtContent></w:sdt>"
        "</w:txbxContent></v:textbox></v:shape></w:pict></w:r></w:p>",
        _p("Footnote line after the box."),
    ]


def ministry_form(seed: int) -> list[str]:
    """Ministry templates carried tables, fields and checkboxes."""
    rows = [["Field", "Value"], ["Case id", f"2025-{seed:04d}"], ["Applicant", "N/A"]]
    table = synth._table(rows)
    checkbox = (
        '<w:p><w:r><w:sym w:font="Wingdings" w:char="F0FE"/></w:r>'
        "<w:r><w:t> I confirm the above</w:t></w:r></w:p>"
    )
    field = (
        '<w:p><w:fldSimple w:instr=" DATE \\@ &quot;dd-MM-yyyy&quot; ">'
        "<w:r><w:t>01-06-2025</w:t></w:r></w:fldSimple></w:p>"
    )
    return [_p(_variant(seed, "Application form")), table, checkbox, field]


def paste_artifact(seed: int) -> list[str]:
    """Pasted text arrives as many small runs with tabs and breaks, which is
    where the spacing complaints started."""
    runs = []
    for index in range(1, 9):
        runs.append("<w:r><w:t>pasted fragment</w:t></w:r><w:r><w:tab/></w:r>")
        if index % 3 == 0:
            runs.append("<w:r><w:br/></w:r>")
    return [_p(_variant(seed, "Pasted content:")), "<w:p>" + "".join(runs) + "</w:p>"]


CONSTRUCTS = {
    "dk-georgia-template": georgia_template,
    "dk-tracked-changes-heavy": tracked_changes_heavy,
    "dk-line-spacing-mixed": line_spacing_mixed,
    "dk-cross-agency-blank": cross_agency_blank,
    "dk-ministry-form": ministry_form,
    "dk-paste-artifact": paste_artifact,
}

# The reported symptom each construct reconstructs, and where it was reported.
SYMPTOMS = {
    "dk-georgia-template": "Georgia in the template; no metric-compatible clone, so line breaks move",
    "dk-tracked-changes-heavy": "track changes difficult to accept",
    "dk-line-spacing-mixed": "odd line spacing when pasting",
    "dk-cross-agency-blank": "documents from other agencies opened blank",
    "dk-ministry-form": "ministry templates with tables, fields and checkboxes",
    "dk-paste-artifact": "pasted text with fragmented runs, tabs and breaks",
}


def write(construct: str, seed: int, path: Path) -> Path:
    body = "".join(CONSTRUCTS[construct](seed))
    path.parent.mkdir(parents=True, exist_ok=True)
    synth.write_body(body, path)
    return path


def write_all(out_dir: Path, variants: int = 2) -> list[Path]:
    paths = []
    for construct in CONSTRUCTS:
        for seed in range(1, variants + 1):
            paths.append(write(construct, seed, out_dir / f"{construct}-{seed}.docx"))
    return paths
