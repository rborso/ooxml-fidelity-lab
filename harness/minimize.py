"""Delta-debug a DOCX down to the smallest document that still fails.

A 40-page letter is not a bug report. ddmin over the body elements turns it
into one, and the reduced file is what gets attached upstream and committed as a
regression fixture.

The render predicate is injected, so the algorithm can be tested without Word.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
DOCUMENT = "word/document.xml"


def read_body(src: Path) -> tuple[list, bytes]:
    """Return the body's non-`sectPr` children, in document order."""
    with zipfile.ZipFile(src) as archive:
        xml = archive.read(DOCUMENT)
    body = etree.fromstring(xml).find(f"{{{W}}}body")
    children = [child for child in body if not child.tag.endswith("}sectPr")]
    return children, xml


def write_subset(src: Path, dst: Path, keep: set[int]) -> Path:
    """Copy `src` to `dst`, keeping only body children whose index is in `keep`."""
    with zipfile.ZipFile(src) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}

    tree = etree.fromstring(entries[DOCUMENT])
    body = tree.find(f"{{{W}}}body")
    children = [child for child in body if not child.tag.endswith("}sectPr")]
    for index, child in enumerate(children):
        if index not in keep:
            body.remove(child)
    entries[DOCUMENT] = etree.tostring(tree, xml_declaration=True, encoding="UTF-8", standalone=True)

    dst.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return dst


def ddmin(count: int, fails) -> list[int]:
    """Classic ddmin over indices. `fails(indices) -> bool` must be monotone
    enough: removing elements never makes a real failure disappear."""
    keep = list(range(count))
    n = 2
    while len(keep) >= 2:
        size = max(1, len(keep) // n)
        chunks = [keep[i : i + size] for i in range(0, len(keep), size)]
        reduced = False
        for chunk in chunks:
            index = set(chunk)
            rest = [i for i in keep if i not in index]
            if not rest:
                continue
            if fails(rest):
                keep = rest
                n = max(n - 1, 2)
                reduced = True
                break
        if not reduced:
            if n >= len(keep):
                break
            n = min(n * 2, len(keep))
    return keep


def minimize_docx(src: Path, dst: Path, predicate, max_candidates: int = 400) -> dict:
    """Reduce `src` until `predicate(path)` stops holding.

    The predicate receives a temporary DOCX and returns True if it still fails.
    """
    children, _ = read_body(src)
    tried = 0

    def fails(indices: list[int]) -> bool:
        nonlocal tried
        if tried >= max_candidates:
            return False
        tried += 1
        scratch = dst.with_name(dst.stem + ".candidate.docx")
        write_subset(src, scratch, set(indices))
        try:
            return bool(predicate(scratch))
        finally:
            scratch.unlink(missing_ok=True)

    if not fails(list(range(len(children)))):
        raise ValueError("predicate does not hold on the source document")

    keep = ddmin(len(children), fails)
    write_subset(src, dst, set(keep))
    return {
        "elements_before": len(children),
        "elements_after": len(keep),
        "candidates_tried": tried,
        "out": str(dst),
    }
