"""Extract a subset of a document's body by construct.

One document with two causes is untriageable: fix either one and the row stays
red, which reads as failure. Splitting the body into per-construct documents
turns "this file has problems" into "this construct has a problem".
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
DOCUMENT = "word/document.xml"


def _matches(element, needles: list[str], mode: str) -> bool:
    serialized = etree.tostring(element, encoding="unicode")
    if mode == "any":
        return any(needle in serialized for needle in needles)
    return all(needle in serialized for needle in needles)


def _trim_trailing_page_breaks(body) -> int:
    """Drop page breaks that have no content after them.

    A break exists to push content onto a new page. Once the extraction removes
    that content the break produces an empty page, which is an artefact of the
    split rather than a property of the document - and an empty page in a bug
    report is just noise.
    """
    removed = 0
    for br in [b for b in body.iter(f"{{{W}}}br") if b.get(f"{{{W}}}type") == "page"]:
        following = False
        seen = False
        for element in body.iter():
            if element is br:
                seen = True
                continue
            if seen and element.tag in (f"{{{W}}}p", f"{{{W}}}tbl"):
                if "".join(element.itertext()).strip():
                    following = True
                    break
        if not following:
            parent = br.getparent()
            if parent is not None:
                parent.remove(br)
                removed += 1
    return removed


def extract(src: Path, dst: Path, needles: list[str], mode: str = "all") -> dict:
    """Keep only body children whose XML contains the given substrings.

    `sectPr` is always kept: without it the page size falls back to each
    engine's default and every line break changes for an unrelated reason.
    """
    with zipfile.ZipFile(src) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}

    tree = etree.fromstring(entries[DOCUMENT])
    body = tree.find(f"{{{W}}}body")
    children = list(body)
    kept = 0
    removed = 0

    for child in children:
        if child.tag.endswith("}sectPr"):
            continue
        if _matches(child, needles, mode):
            kept += 1
        else:
            body.remove(child)
            removed += 1

    # Word merges two adjacent tables into one, so removing the paragraphs that
    # separated them silently changes the document. A single empty paragraph
    # between tables keeps them apart, which is what a user does by hand.
    previous = None
    for child in list(body):
        if child.tag.endswith("}sectPr"):
            continue
        if (
            previous is not None
            and previous.tag == f"{{{W}}}tbl"
            and child.tag == f"{{{W}}}tbl"
        ):
            body.insert(body.index(child), etree.Element(f"{{{W}}}p"))
        previous = child

    breaks_removed = _trim_trailing_page_breaks(body)

    entries[DOCUMENT] = etree.tostring(
        tree, xml_declaration=True, encoding="UTF-8", standalone=True
    )
    dst.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)

    return {"source": str(src), "out": str(dst), "kept": kept, "removed": removed,
            "page_breaks_removed": breaks_removed}
