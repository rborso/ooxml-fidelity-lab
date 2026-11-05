#!/usr/bin/env python3
"""Serve the report site, rebuilding it when runs or families change.

Deliberately boring: a static directory and a conditional rebuild. Internal
use only, so it binds to one address and has no auth, no TLS, and no writes.

    serve.py --bind 172.16.10.2 --port 8080
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.site import build_from_repo  # noqa: E402

_lock = threading.Lock()
_last_check = 0.0
_signature = None


def _newest(*dirs: Path) -> float:
    newest = 0.0
    for directory in dirs:
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            try:
                newest = max(newest, path.stat().st_mtime)
            except OSError:
                continue
    return newest


def _source_signature() -> float:
    return max(
        _newest(REPO / "private" / "runs"),
        _newest(REPO / "docs" / "families"),
    )


def maybe_rebuild(force: bool = False) -> None:
    """Rebuild if the sources are newer than the last build. Cheap enough to
    call on each page request, with a short debounce."""
    global _last_check, _signature
    now = time.monotonic()
    with _lock:
        if not force and now - _last_check < 2.0:
            return
        _last_check = now
        signature = _source_signature()
        if not force and signature == _signature:
            return
        try:
            info = build_from_repo(REPO)
            _signature = signature
            print(f"rebuilt: {info}", file=sys.stderr, flush=True)
        except Exception as exc:  # keep serving the previous build
            print(f"rebuild failed: {exc}", file=sys.stderr, flush=True)


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/", "/index.html", "/runs.html", "/families.html"):
            maybe_rebuild()
        super().do_GET()

    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.address_string()} {fmt % args}", file=sys.stderr, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="serve the fidelity report site")
    parser.add_argument("--bind", default=os.environ.get("SITE_BIND", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("SITE_PORT", "8080")))
    parser.add_argument("--root", default=str(REPO / "private" / "site"))
    args = parser.parse_args()

    root = Path(args.root)
    maybe_rebuild(force=True)
    if not (root / "index.html").exists():
        print("site build produced no index.html", file=sys.stderr)
        return 1

    handler = lambda *a, **kw: Handler(*a, directory=str(root), **kw)  # noqa: E731
    server = ThreadingHTTPServer((args.bind, args.port), handler)
    print(f"serving {root} on http://{args.bind}:{args.port}", file=sys.stderr, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
