#!/usr/bin/env bash
# Bootstrap a clean host for the OOXML fidelity harness.
#   ./scripts/host/bootstrap.sh
# Idempotent: safe to re-run.
set -euo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$REPO"

echo "== python =="
if [ ! -d .venv ]; then
  python3.12 -m venv .venv
fi
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q \
  pymupdf lxml python-docx pydantic pyyaml typer duckdb pikepdf \
  imagehash pillow pytest markdown

echo "== private tree =="
mkdir -p private/{config,corpus,artifacts,runs,reports,vm,host}
[ -f private/config/oracle.yaml ]    || cp config/oracle.example.yaml    private/config/oracle.yaml
[ -f private/config/renderers.yaml ] || cp config/renderers.example.yaml private/config/renderers.yaml
chmod 700 private

echo "== container runtime =="
if command -v podman >/dev/null 2>&1; then
  podman --version
elif command -v docker >/dev/null 2>&1; then
  docker --version
else
  echo "WARNING: no podman or docker; renderers will not run" >&2
fi

echo "== optional tooling =="
command -v pdftotext >/dev/null 2>&1 || echo "note: install poppler-utils for crosscheck"
command -v ntfs-3g   >/dev/null 2>&1 || echo "note: install ntfs-3g for offline staging"

echo "== harness self-test =="
.venv/bin/python -m pytest -q

echo
echo "next: make gate && make site"
