"""Ask which stage lost the content, using conversions as probes.

Before any trace: convert the document to progressively lower-fidelity formats and
look for the text. Each conversion goes through the same import, so the first
format that is missing the text names the stage.

    txt   the document model itself
    odt   the native format, after import and before layout
    docx  a full round trip through both

If every probe is missing the text, import dropped it. If only the PDF is
missing it, layout or export did. That distinction halves the search before a
single line of C++ is read.
"""

from __future__ import annotations

import subprocess
import tempfile
import zipfile
from pathlib import Path

FORMATS = ("txt", "odt", "docx")


class ProbeError(RuntimeError):
    pass


def _convert(docx: Path, fmt: str, binary: str, out: Path, timeout: int) -> Path | None:
    try:
        subprocess.run(
            [binary, "--headless", "--norestore", "--convert-to", fmt,
             "--outdir", str(out), str(docx)],
            capture_output=True, timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProbeError(f"convert to {fmt} failed: {exc}") from exc
    produced = sorted(out.glob(f"*.{fmt}"))
    return produced[0] if produced else None


def _text_of(path: Path) -> str:
    if path.suffix == ".txt":
        return path.read_text(encoding="utf-8", errors="replace")
    member = "content.xml" if path.suffix == ".odt" else "word/document.xml"
    try:
        with zipfile.ZipFile(path) as z:
            return z.read(member).decode("utf-8", errors="replace")
    except (KeyError, zipfile.BadZipFile, OSError):
        return ""


def probe(docx: Path, token: str, binary: str, timeout: int = 180) -> dict:
    """Where does `token` survive? Returns one entry per format."""
    docx = docx.resolve()
    if not docx.exists():
        raise ProbeError(f"no such document: {docx}")
    if not Path(binary).exists():
        raise ProbeError(f"no such binary: {binary}")

    results = {}
    for fmt in FORMATS:
        with tempfile.TemporaryDirectory(prefix=f"probe-{fmt}-") as tmp:
            produced = _convert(docx, fmt, binary, Path(tmp), timeout)
            text = _text_of(produced) if produced else ""
            results[fmt] = {
                "produced": bool(produced),
                "found": token in text,
                "occurrences": text.count(token),
            }
    return {"document": docx.name, "token": token, "stages": results,
            "verdict": verdict(results)}


def verdict(results: dict) -> str:
    if not results.get("txt", {}).get("found"):
        return "import"          # never reached the document model
    if not results.get("odt", {}).get("found"):
        return "import-to-native"  # lost on the way into the native format
    if not results.get("docx", {}).get("found"):
        return "round-trip"      # survives import, lost on export
    return "later-stage"         # present in all probes: layout or PDF export
