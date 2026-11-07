"""Delta-debug a DOCX down to the smallest document that still fails.

A 40-page form is not a bug report. This deletes parts of `word/document.xml`
and keeps the deletion if the symptom survives, so what comes out is the
smallest document that still fails.

The oracle for "still fails" is the renderer itself, injected as a predicate so
the algorithm can be tested without Word.

Three rules, each learned by watching this tool produce a confident wrong
answer:

- the token under investigation must still be *present* in the document, or the
  reducer deletes the evidence and converges on an empty file;
- it must still be present the *same number of times*, or one of Word's
  `mc:Choice`/`mc:Fallback` duplicates gets deleted;
- only content is removable. Deleting property elements changes which code path
  the renderer takes, and the "confirmed cause" that produced was an artefact of
  the reducer.

lxml is used deliberately: it round-trips namespace prefixes, and `mc:Ignorable`
refers to prefixes by name.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
DOCUMENT = "word/document.xml"

REMOVABLE = {
    f"{{{W}}}p", f"{{{W}}}r", f"{{{W}}}tbl", f"{{{W}}}tr", f"{{{W}}}tc",
    f"{{{W}}}drawing", f"{{{W}}}pict", f"{{{W}}}bookmarkStart", f"{{{W}}}bookmarkEnd",
    f"{{{W}}}proofErr", f"{{{W}}}commentRangeStart", f"{{{W}}}commentRangeEnd",
    f"{{{W}}}hyperlink", f"{{{W}}}sdt",
}
DESCEND = {
    f"{{{W}}}body", f"{{{W}}}p", f"{{{W}}}tbl", f"{{{W}}}tr", f"{{{W}}}tc", f"{{{W}}}r",
}


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

    Word splits words across runs, so searching the raw markup would say the
    text was never there.
    """
    with zipfile.ZipFile(path) as archive:
        root = etree.fromstring(archive.read(DOCUMENT))
    return "".join(node.text or "" for node in root.iter(f"{{{W}}}t"))


def render_text(binary: str, path: Path, workdir: Path) -> str | None:
    """Convert to PDF and return its text, or None if the render failed."""
    import subprocess

    for old in workdir.glob("*.pdf"):
        old.unlink()
    try:
        subprocess.run(
            [binary, "--headless", "--norestore", "--convert-to", "pdf",
             "--outdir", str(workdir), str(path)],
            capture_output=True, timeout=180, check=False,
        )
        produced = list(workdir.glob("*.pdf"))
        if not produced:
            return None
        return subprocess.run(["pdftotext", str(produced[0]), "-"],
                              capture_output=True, text=True, timeout=120).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None


def render_predicate(binary: str, token: str, workdir: Path, keep_count: bool = True,
                     control: str | None = None):
    """The token must be in the document and missing from the rendered PDF.

    The probe is the PDF, not `--convert-to txt`: on bz55459 the txt export
    returns nothing while the PDF renders the text 21 times, so a txt-based
    predicate reports "missing" for a document that renders correctly.

    `control` is a second token that must keep rendering. Without it a reducer
    can delete the paragraph a shape is anchored to, or empty the document, and
    "the token is missing" still holds - the reduction then proves nothing. With
    it, every candidate has to stay a document that renders something.
    """
    import subprocess

    workdir.mkdir(parents=True, exist_ok=True)
    expected: list[int] = []

    def predicate(path: Path) -> bool:
        try:
            text = document_text(path)
        except (KeyError, zipfile.BadZipFile, OSError, etree.XMLSyntaxError):
            return False
        count = text.count(token)
        if count == 0:
            return False
        if keep_count:
            if not expected:
                expected.append(count)   # first call is the source document
            elif count != expected[0]:
                return False
        rendered = render_text(binary, path, workdir)
        if rendered is None:
            return False
        if control and control not in rendered:
            return False
        return token not in rendered

    return predicate


def _reduce(src: Path, dst: Path, predicate, max_candidates: int,
            removable: set[str], descend: set[str],
            skip_children_of: str | None) -> dict:
    """Shared loop: try removing children, keep the removal that still fails."""
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
    while queue and tried < max_candidates:
        parent = queue.pop(0)
        if parent.tag not in descend:
            continue
        if skip_children_of and parent.tag == skip_children_of:
            continue
        for child in list(parent):
            if tried >= max_candidates:
                break
            if child.tag not in removable or len(child) == 0:
                continue
            index = parent.index(child)
            parent.remove(child)
            if fails():
                continue
            parent.insert(index, child)
            queue.append(child)

    write_subset_raw(src, dst, root)
    return {"elements_before": before, "elements_after": sum(1 for _ in root.iter()),
            "candidates_tried": tried, "out": str(dst)}


def minimize_content(src: Path, dst: Path, predicate, max_candidates: int = 200) -> dict:
    """Remove content items only, keeping every property element intact."""
    return _reduce(src, dst, predicate, max_candidates, REMOVABLE, DESCEND, None)


def minimize_deep(src: Path, dst: Path, predicate, max_candidates: int = 150) -> dict:
    """Remove any subtree, but never break an mc:Choice / mc:Fallback pair.

    Deleting a Choice leaves a Fallback-only block: invalid, a different code
    path in the renderer, and a bug that is not the one under investigation.
    """
    class Any:
        def __contains__(self, _):
            return True
    return _reduce(src, dst, predicate, max_candidates, Any(), Any(), f"{{{MC}}}AlternateContent")


def minimize_docx(src: Path, dst: Path, predicate, max_candidates: int = 400) -> dict:
    """Reduce body-level children with ddmin. Kept for the simple cases."""
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
