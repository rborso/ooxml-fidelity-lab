"""Round-trip testing: what happens to a document after it is saved again.

Two things are measured, and they are different:

  convergence - does repeated open/save reach a fixed point? A document that
                keeps changing is structurally unstable and unsafe in a mixed
                authoring workflow.
  churn       - how much the XML changes on each hop.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
DOCUMENT = "word/document.xml"

COLLABORA_IMAGE = (
    "docker.io/collabora/code@sha256:"
    "808410e77b8695a35b93c7638fbba07c10cf0ba8307141b460248f18ab6e5c55"
)
ENTRYPOINT = "/opt/collaboraoffice/program/soffice.bin"

# rsids are editing-session ids. They change on every save by design, so they
# must be normalised before any comparison or every hop looks like churn.
RSID = re.compile(r'\s+w:rsid[A-Za-z]*="[^"]*"')


def normalize(xml: bytes) -> bytes:
    text = xml.decode("utf-8", "replace")
    text = RSID.sub("", text)
    return text.encode()


def signature(docx: Path) -> str:
    with zipfile.ZipFile(docx) as archive:
        try:
            xml = archive.read(DOCUMENT)
        except KeyError:
            return "no-document-part"
    return hashlib.sha256(normalize(xml)).hexdigest()


def text_of(docx: Path) -> str:
    with zipfile.ZipFile(docx) as archive:
        xml = archive.read(DOCUMENT)
    tree = etree.fromstring(xml)
    return " ".join(tree.itertext())


def mutate(src: Path, dst: Path, seed: int = 0) -> Path:
    """Deterministic edit: append one paragraph. Same seed, same output."""
    with zipfile.ZipFile(src) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}

    tree = etree.fromstring(entries[DOCUMENT])
    body = tree.find(f"{{{W}}}body")
    paragraph = etree.SubElement(body, f"{{{W}}}p")
    run = etree.SubElement(paragraph, f"{{{W}}}r")
    node = etree.SubElement(run, f"{{{W}}}t")
    node.text = f"lab edit {seed}"

    entries[DOCUMENT] = etree.tostring(
        tree, xml_declaration=True, encoding="UTF-8", standalone=True
    )
    dst.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return dst


def convert(src: Path, target: str, out_dir: Path, timeout: int = 180) -> Path:
    """Convert through the Collabora engine. target is 'docx' or 'odt'."""
    src = src.resolve()
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    runtime = shutil.which("podman") or shutil.which("docker")
    if not runtime:
        raise RuntimeError("neither podman nor docker found")
    cmd = [
        runtime, "run", "--rm",
        "--user", "0",
        "-e", "HOME=/tmp",
        "-v", f"{src.parent}:/in:Z",
        "-v", f"{out_dir}:/out:Z",
        "--entrypoint", ENTRYPOINT,
        COLLABORA_IMAGE,
        "--headless", "--norestore",
        "--convert-to", target,
        "--outdir", "/out",
        f"/in/{src.name}",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    produced = out_dir / f"{src.stem}.{target}"
    if not produced.exists():
        raise RuntimeError(f"conversion to {target} failed: {proc.stderr[-400:]}")
    return produced


def convergence(docx: Path, work: Path, hops: int = 5) -> dict:
    """Repeated open/save until the document stops changing."""
    work.mkdir(parents=True, exist_ok=True)
    current = Path(docx)
    seen = [signature(current)]
    converged_at = None

    for hop in range(1, hops + 1):
        converted = convert(current, "docx", work / f"hop{hop}")
        moved = work / f"hop{hop}-in.docx"
        shutil.copy2(converted, moved)
        current = moved
        digest = signature(current)
        seen.append(digest)
        if digest == seen[-2]:
            converged_at = hop
            break

    return {
        "hops": len(seen) - 1,
        "converged_at": converged_at,
        "converged": converged_at is not None,
        "signatures": seen,
        "final": str(current),
    }


def format_churn(docx: Path, work: Path) -> dict:
    """DOCX -> ODT -> DOCX: cross-format loss, which pass-through does not see."""
    work.mkdir(parents=True, exist_ok=True)
    odt = convert(docx, "odt", work / "to-odt")
    back = convert(odt, "docx", work / "to-docx")
    before, after = signature(docx), signature(back)
    return {
        "odt": str(odt),
        "back": str(back),
        "changed": before != after,
        "text_before": len(text_of(docx)),
        "text_after": len(text_of(back)),
    }
