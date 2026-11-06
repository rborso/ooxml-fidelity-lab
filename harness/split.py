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

    entries[DOCUMENT] = etree.tostring(
        tree, xml_declaration=True, encoding="UTF-8", standalone=True
    )
    dst.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)

    return {"source": str(src), "out": str(dst), "kept": kept, "removed": removed}
