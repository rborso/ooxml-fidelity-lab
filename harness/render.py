"""Renderer adapters.

Everything renders to PDF through an adapter with the same shape, so the oracle
can be swapped without touching the pipeline. Until the Windows oracle exists,
`stub_oracle` is simply the Collabora engine — useful for proving the pipeline,
useless for real fidelity scores.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

# Pinned. A floating tag destroys comparability between runs.
COLLABORA_IMAGE = (
    "docker.io/collabora/code@sha256:"
    "808410e77b8695a35b93c7638fbba07c10cf0ba8307141b460248f18ab6e5c55"
)
COLLABORA_ENTRYPOINT = "/opt/collaboraoffice/program/soffice.bin"


class RenderError(RuntimeError):
    pass


def _podman() -> str:
    for exe in ("podman", "docker"):
        if shutil.which(exe):
            return exe
    raise RenderError("neither podman nor docker found")


def render_collabora(
    docx: Path, out_dir: Path, image: str = COLLABORA_IMAGE, timeout: int = 180
) -> Path:
    """Convert a DOCX to PDF using the Collabora engine inside the pinned image."""
    docx = docx.resolve()
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf = out_dir / (docx.stem + ".pdf")

    cmd = [
        _podman(), "run", "--rm",
        "--user", "0",
        "-e", "HOME=/tmp",
        "-v", f"{docx.parent}:/in:Z",
        "-v", f"{out_dir}:/out:Z",
        "--entrypoint", COLLABORA_ENTRYPOINT,
        image,
        "--headless", "--norestore",
        "--convert-to", "pdf",
        "--outdir", "/out",
        f"/in/{docx.name}",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise RenderError(f"render timed out after {timeout}s: {docx.name}") from exc

    if not pdf.exists():
        raise RenderError(
            f"no PDF produced for {docx.name} (exit {proc.returncode})\n"
            f"{(proc.stderr or proc.stdout)[-800:]}"
        )
    return pdf


def stub_oracle(docx: Path, out_dir: Path) -> Path:
    """Stand-in for Microsoft Word. Identical engine, so deltas are zero.

    This exists to exercise the pipeline before the Windows VM is ready. Any
    report produced with it is a determinism check, not a fidelity score.
    """
    return render_collabora(docx, out_dir)
