"""Group failures by the OOXML constructs they contain.

The unit of work is a family, not a document. A construct signature is a stable
description of what a document exercises, hashed, so two documents with the same
problem land in the same bucket across runs.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
DOCUMENT = "word/document.xml"

# Constructs that plausibly explain a rendering difference. Counting them is
# cheap and stable; a full element histogram would be noise.
INTERESTING = [
    "tbl", "txbxContent", "sdt", "fldSimple", "fldChar", "instrText",
    "drawing", "pict", "object", "numPr", "numbering", "hyperlink",
    "footnoteReference", "endnoteReference", "commentReference", "br",
    "tblStylePr", "tblLook", "tblpPr", "framePr", "oMath", "oMathPara",
    "pgNumType", "sectPr", "headerReference", "footerReference", "vMerge",
    "gridSpan", "cantSplit", "keepNext", "widowControl", "snapToGrid",
]


def construct_signature(docx: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    try:
        with zipfile.ZipFile(docx) as archive:
            xml = archive.read(DOCUMENT)
    except (zipfile.BadZipFile, KeyError, OSError):
        return {"unreadable": 1}

    tree = etree.fromstring(xml)
    names = {name: f"{{{W}}}{name}" for name in INTERESTING}

    for element in tree.iter():
        tag = element.tag
        for name, full in names.items():
            if tag == full:
                counts[name] = counts.get(name, 0) + 1
                break
    return dict(sorted(counts.items()))


def signature_hash(counts: dict[str, int]) -> str:
    payload = json.dumps(counts, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def describe(counts: dict[str, int], limit: int = 5) -> str:
    if not counts:
        return "no tracked constructs"
    top = sorted(counts.items(), key=lambda kv: -kv[1])[:limit]
    return ", ".join(f"{name}x{count}" for name, count in top)


def cluster(documents: list[tuple[str, Path, str]]) -> list[dict]:
    """Group (id, path, tier) by signature. Returns clusters ordered by size."""
    groups: dict[str, dict] = {}
    for doc_id, path, tier in documents:
        counts = construct_signature(path)
        key = signature_hash(counts)
        group = groups.setdefault(
            key,
            {"key": key, "tier": tier, "constructs": counts, "documents": []},
        )
        group["documents"].append(doc_id)

    clusters = sorted(groups.values(), key=lambda g: -len(g["documents"]))
    for group in clusters:
        group["size"] = len(group["documents"])
        group["description"] = describe(group["constructs"])
    return clusters
