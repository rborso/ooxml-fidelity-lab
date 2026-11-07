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


def document_text(path: Path) -> str:
    """Concatenated text of every w:t, ignoring run boundaries.

    A token that Word splits across runs never appears as a contiguous string in
    the XML, so searching the raw markup would say the text was never there.
    """
    with zipfile.ZipFile(path) as archive:
        xml = archive.read(DOCUMENT)
    root = etree.fromstring(xml)
    parts = [node.text or "" for node in root.iter(f"{{{W}}}t")]
    return "".join(parts)


def render_predicate(binary: str, token: str, workdir: Path, keep_count: bool = True):
    """The token must be in the document and missing from the render.

    "Missing from the render" alone is degenerate: deleting the paragraph that
    carries the text keeps it missing, so the minimizer happily deletes the very
    content under investigation and converges on an empty document that proves
    nothing. Requiring the token to still be present in the source makes every
    deletion a decision about the surviving text.

    `keep_count` also pins how many times the token occurs. Word duplicates a
    shape's text into both `mc:Choice` and `mc:Fallback`; without the count the
    minimizer deletes the Choice and keeps the Fallback, producing a document
    that Word would render and LibreOffice drops - a different bug than the one
    being investigated, arrived at by accident.
    """
    import subprocess

    workdir.mkdir(parents=True, exist_ok=True)
    expected: list[int] = []

    def predicate(path: Path) -> bool:
        try:
            text = document_text(path)
        except (KeyError, zipfile.BadZipFile, OSError):
            return False
        count = text.count(token)
        if count == 0:
            return False
        if keep_count:
            if not expected:
                expected.append(count)   # first call is the source document
            elif count != expected[0]:
                return False
        for old in workdir.glob("*.txt"):
            old.unlink()
        try:
            subprocess.run(
                [binary, "--headless", "--norestore", "--convert-to", "txt",
                 "--outdir", str(workdir), str(path)],
                capture_output=True, timeout=180, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        produced = list(workdir.glob("*.txt"))
        if not produced:
            return False
        return token not in produced[0].read_text(encoding="utf-8", errors="replace")

    return predicate


def minimize_deep(src: Path, dst: Path, predicate, max_candidates: int = 150) -> dict:
    """Reduce any subtree, not just body children.

    ddmin over body children cannot isolate a construct nested inside a shape:
    the whole paragraph is either kept or dropped, and the paragraph is the
    document. This removes arbitrary subtrees instead, deepest-first in effect,
    because a container is only queued once its parent refused to drop it.

    lxml is used deliberately: it round-trips namespace prefixes unchanged, and
    `mc:Ignorable` refers to prefixes by name.
    """
    with zipfile.ZipFile(src) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    root = etree.fromstring(entries[DOCUMENT])
    body = root.find(f"{{{W}}}body")
    before = sum(1 for _ in root.iter())
    tried = 0

    def fails() -> bool:
        nonlocal tried
        if tried >= max_candidates:
            return False
        tried += 1
        scratch = dst.with_name(dst.stem + ".candidate.docx")
        entries[DOCUMENT] = etree.tostring(root, xml_declaration=True,
                                           encoding="UTF-8", standalone=True)
        with zipfile.ZipFile(scratch, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, data in entries.items():
                archive.writestr(name, data)
        try:
            return bool(predicate(scratch))
        finally:
            scratch.unlink(missing_ok=True)

    if not fails():
        raise ValueError("predicate does not hold on the source document")

    queue = [body]
    MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
    while queue and tried < max_candidates:
        parent = queue.pop(0)
        # Never break an AlternateContent pair. Word duplicates the same content
        # into mc:Choice and mc:Fallback, and deleting the Choice leaves a
        # Fallback-only block, which is invalid, changes which code path the
        # renderer takes, and manufactures a bug that is not the one under
        # investigation. The first run of this reducer did exactly that and the
        # "confirmed cause" it produced was an artefact of the reducer.
        if parent.tag == MC + "AlternateContent":
            continue
        for child in list(parent):
            if tried >= max_candidates:
                break
            if len(child) == 0:
                continue
            index = parent.index(child)
            parent.remove(child)
            if fails():
                continue
            parent.insert(index, child)
            queue.append(child)

    write_subset_raw(src, dst, root)
    return {
        "elements_before": before,
        "elements_after": sum(1 for _ in root.iter()),
        "candidates_tried": tried,
        "out": str(dst),
    }


def write_subset_raw(src: Path, dst: Path, root) -> None:
    """Write `dst` from `src`, replacing document.xml with the given tree."""
    with zipfile.ZipFile(src) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    entries[DOCUMENT] = etree.tostring(root, xml_declaration=True,
                                       encoding="UTF-8", standalone=True)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)


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
