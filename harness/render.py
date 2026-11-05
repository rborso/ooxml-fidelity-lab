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


ONLYOFFICE_IMAGE = "docker.io/onlyoffice/documentserver"


def onlyoffice_available(url: str | None = None) -> tuple[bool, str]:
    """Probe a Document Server. Returns (available, reason)."""
    import os
    import urllib.error
    import urllib.request

    url = url or os.environ.get("ONLYOFFICE_URL")
    if not url:
        return (
            False,
            "ONLYOFFICE_URL is not set: start onlyoffice/documentserver and point "
            "ONLYOFFICE_URL at it, then restart this process",
        )
    probe = url.rstrip("/") + "/healthcheck"
    try:
        with urllib.request.urlopen(probe, timeout=8) as response:
            if response.status == 200:
                return True, "ok"
            return False, f"{probe} returned {response.status}"
    except urllib.error.URLError as exc:
        return False, f"{url} is unreachable: {exc.reason}"
    except OSError as exc:
        return False, f"{url} is unreachable: {exc}"


def render_onlyoffice(docx: Path, out_dir: Path, url: str | None = None,
                      port: int = 8099, timeout: int = 180) -> Path:
    """Convert through a running ONLYOFFICE Document Server.

    The server fetches the document over HTTP rather than accepting an upload,
    so this starts a one-shot file server on the host and points the conversion
    request at it. For the container to reach it, run the Document Server with
    --network=host, or use an address it can route to.
    """
    import json
    import threading
    import urllib.request
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    available, reason = onlyoffice_available(url)
    if not available:
        raise RenderError(reason)

    docx = docx.resolve()
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf = out_dir / (docx.stem + ".pdf")

    handler = lambda *a, **kw: SimpleHTTPRequestHandler(*a, directory=str(docx.parent), **kw)
    server = ThreadingHTTPServer(("0.0.0.0", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        payload = json.dumps(
            {
                "async": False,
                "filetype": docx.suffix.lstrip(".").lower(),
                "outputtype": "pdf",
                "title": docx.name,
                "url": f"http://127.0.0.1:{port}/{docx.name}",
            }
        ).encode()
        request = urllib.request.Request(
            (url or "").rstrip("/") + "/ConvertService.ashx",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
    finally:
        server.shutdown()
        server.server_close()

    try:
        result = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RenderError(f"OnlyOffice returned non-JSON: {body[:200]!r}") from exc

    if result.get("error"):
        raise RenderError(f"OnlyOffice error {result.get('error')}: {result}")
    remote = result.get("fileUrl")
    if not remote:
        raise RenderError(f"OnlyOffice returned no fileUrl: {result}")

    with urllib.request.urlopen(remote, timeout=timeout) as response:
        pdf.write_bytes(response.read())
    return pdf
