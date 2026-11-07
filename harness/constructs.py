"""Construct index: which documents contain what.

A family is a construct crossed with a difference signature. The signature half
comes from a run; the construct half has to come from the documents themselves,
or "which other documents have this bug" is answered by opening files until it
feels done.

Extracts, for every document, the element paths that matter (ancestor chain of
local names, namespace prefixes dropped) plus counts of the constructs that
recur in our families. The result is a small JSON index that can be queried.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

# Keys are the last four ancestors, so depth does not inflate the index; the
# nesting that matters (sdt inside txbxContent inside pict) is already deeper
# than any fixed cap would allow if the cap applied to the walk.
PATH_DEPTH = 4

INTERESTING = (
    "sdt", "sdtPr", "txbxContent", "txbx", "pict", "drawing", "tbl", "tr", "tc",
    "hyperlink", "fldSimple", "instrText", "numPr", "sectPr", "footnoteReference",
    "endnoteReference", "AlternateContent", "object", "pPr", "rPr",
)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def signature(docx: Path) -> dict:
    """Element paths and construct counts for one document."""
    try:
        with zipfile.ZipFile(docx) as zf:
            raw = zf.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile, OSError) as exc:
        raise ValueError(f"cannot read {docx.name}: {exc}") from exc

    paths: dict[str, int] = {}
    counts: dict[str, int] = {}
    stack: list[str] = []

    for event, elem in ET.iterparse(_bytes_reader(raw), events=("start", "end")):
        name = _local(elem.tag)
        if event == "start":
            stack.append(name)
            if name in INTERESTING:
                counts[name] = counts.get(name, 0) + 1
            if len(stack) >= 2:
                key = " > ".join(stack[-PATH_DEPTH:])
                paths[key] = paths.get(key, 0) + 1
        else:
            stack.pop()
            elem.clear()

    return {"counts": counts, "paths": paths}


def _bytes_reader(raw: bytes):
    """iterparse needs a file object; ET.fromstring would build the whole tree."""
    import io
    return io.BytesIO(raw)


def build(docs: list[Path], out: Path, names: dict[str, str] | None = None) -> dict:
    """Index documents, keyed by corpus id when one is known.

    Runs identify documents by manifest id, not by filename, so indexing by stem
    produced a set that could not be joined to a result set at all.
    """
    index = {}
    for docx in docs:
        key = (names or {}).get(str(docx), docx.stem)
        try:
            index[key] = signature(docx)
        except ValueError as exc:
            index[key] = {"error": str(exc)}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(index, indent=1, sort_keys=True))
    return index


def load(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def query(index: dict, pattern: str) -> list[str]:
    """Documents whose construct paths contain every term, in any order.

    `query(idx, "txbxContent sdt")` finds sdt inside a textbox without needing
    the exact path spelling.
    """
    terms = [t.lower() for t in pattern.split()]
    hits = []
    for name, data in index.items():
        if "error" in data:
            continue
        paths = [p.lower() for p in data.get("paths", {})]
        if any(all(term in path for term in terms) for path in paths):
            hits.append(name)
    return sorted(hits)
