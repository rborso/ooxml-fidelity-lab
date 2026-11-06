"""Renderer adapters.

Everything renders to PDF through an adapter with the same shape, so the oracle
can be swapped without touching the pipeline. Until the Windows oracle exists,
`stub_oracle` is simply the Collabora engine — useful for proving the pipeline,
useless for real fidelity scores.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import uuid
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


LABEL = "ooxml-lab=render"


def reap_stale() -> int:
    """Remove containers left behind by a render that timed out.

    `podman run --rm` removes the container when it exits, not when the client is
    killed. A timeout therefore leaves soffice.bin spinning at 100% forever: the
    first one found here had been running for 3h20m on a single document.
    """
    exe = _podman()
    ids = subprocess.run(
        [exe, "ps", "-aq", "--filter", f"label={LABEL}"],
        capture_output=True, text=True,
    ).stdout.split()
    for cid in ids:
        subprocess.run([exe, "rm", "-f", cid], capture_output=True)
    return len(ids)


def render_collabora(
    docx: Path, out_dir: Path, image: str = COLLABORA_IMAGE, timeout: int = 180
) -> Path:
    """Convert a DOCX to PDF using the Collabora engine inside the pinned image."""
    docx = docx.resolve()
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf = out_dir / (docx.stem + ".pdf")

    exe = _podman()
    # A name we own, so a timeout can kill the container rather than just the
    # client that is waiting on it.
    name = f"ooxml-render-{uuid.uuid4().hex[:12]}"
    cmd = [
        exe, "run", "--rm",
        "--name", name,
        "--label", LABEL,
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
        subprocess.run([exe, "rm", "-f", name], capture_output=True)
        raise RenderError(f"render timed out after {timeout}s: {docx.name}") from exc

    if not pdf.exists():
        subprocess.run([exe, "rm", "-f", name], capture_output=True)
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

# Set to a locally built image tagged by digest to measure a patch.
CUSTOM_IMAGE = os.environ.get("CUSTOM_IMAGE")
# Or point straight at a binary from a built source tree; no container needed.
CUSTOM_SOFFICE = os.environ.get("CUSTOM_SOFFICE")
# The unpatched binary from the same tree: the experiment baseline.
CLEAN_SOFFICE = os.environ.get("CLEAN_SOFFICE")
# Point fontconfig at a directory that mirrors the container's font bundle, so
# a built binary is compared on engine behaviour rather than on font packaging.
LO_FONTCONFIG = os.environ.get("LO_FONTCONFIG")


def render_soffice(binary: str, docx: Path, out_dir: Path, timeout: int = 180) -> Path:
    """Convert with a soffice binary from a build tree.

    A throwaway user profile per document stops state leaking between documents,
    the same reason the Windows agent starts a fresh Word each time.
    """
    import tempfile

    docx = docx.resolve()
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf = out_dir / (docx.stem + ".pdf")
    profile = Path(tempfile.mkdtemp(prefix="lo-profile-"))

    env = os.environ.copy()
    if LO_FONTCONFIG:
        env["FONTCONFIG_FILE"] = LO_FONTCONFIG

    cmd = [
        binary,
        f"-env:UserInstallation=file://{profile}",
        "--headless", "--norestore",
        "--convert-to", "pdf",
        "--outdir", str(out_dir),
        str(docx),
    ]
    try:
        # Own session: soffice spawns children, and killing only the parent
        # leaves them holding the document open.
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            start_new_session=True, env=env,
        )
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.communicate()
        raise RenderError(f"render timed out after {timeout}s: {docx.name}") from exc
    finally:
        shutil.rmtree(profile, ignore_errors=True)

    if not pdf.exists():
        raise RenderError(
            f"no PDF produced for {docx.name} (exit {proc.returncode})\n"
            f"{(stderr or stdout or '')[-800:]}"
        )
    return pdf


def render_built_clean(docx: Path, out_dir: Path, timeout: int = 180) -> Path:
    """The unpatched build. The baseline a patch is compared against."""
    if not CLEAN_SOFFICE:
        raise RenderError(
            "CLEAN_SOFFICE is not set: point it at the unpatched binary from the build tree"
        )
    return render_soffice(CLEAN_SOFFICE, docx, out_dir, timeout)


def render_built_patched(docx: Path, out_dir: Path, timeout: int = 180) -> Path:
    """The patched build, from the same tree as the clean one."""
    if not CUSTOM_SOFFICE:
        raise RenderError(
            "CUSTOM_SOFFICE is not set: point it at the patched binary from the build tree"
        )
    return render_soffice(CUSTOM_SOFFICE, docx, out_dir, timeout)


def render_built_patched(docx: Path, out_dir: Path, timeout: int = 180) -> Path:
    """The patched build, from the same tree as the clean one.

    Falls back to a derived container image, which is how the font patch was
    shipped before there was a build tree to relink.
    """
    if CUSTOM_SOFFICE:
        return render_soffice(CUSTOM_SOFFICE, docx, out_dir, timeout)
    if CUSTOM_IMAGE:
        return render_collabora(docx, out_dir, image=CUSTOM_IMAGE, timeout=timeout)
    raise RenderError(
        "no patched build configured: set CUSTOM_SOFFICE to a binary from a built "
        "source tree, or CUSTOM_IMAGE to a derived container image pinned by digest"
    )


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
