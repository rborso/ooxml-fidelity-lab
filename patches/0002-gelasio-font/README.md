# 0002 — ship Gelasio so Georgia substitutes with a metric-compatible clone

Fixes family **0001**. Reproducer: the `georgia` synthetic construct.

## Why this one needs no compiler

The upstream image bundles Carlito (Calibri), Caladea (Cambria), Liberation
(Arial/Times) and a Noto subset. It does **not** bundle Georgia, or any
metric-compatible clone of it. A Georgia run therefore falls back to
`NotoSerif-Regular`, a generic serif with different advances, and every line
break moves.

Gelasio is metric-compatible with Georgia. Adding the file is enough.

## Build

```bash
curl -sL -o Gelasio-VF.ttf \
  "https://github.com/google/fonts/raw/main/ofl/gelasio/Gelasio%5Bwght%5D.ttf"
sha256sum Gelasio-VF.ttf        # record it; the URL is not a version
podman build -t ooxml-lab/collabora:fonts-custom -f Containerfile .
podman image inspect ooxml-lab/collabora:fonts-custom --format '{{.Id}}'
```

The image has no shell, so the Containerfile is `FROM` plus `COPY` only. No
`RUN`, no `fc-cache`. LibreOffice scans its own font directory, so the file is
picked up without a fontconfig refresh.

## Verify

```bash
export CUSTOM_IMAGE=ooxml-lab/collabora:fonts-custom
make run-clean
make run-custom
.venv/bin/python -m harness.cli validate \
  --clean-run private/runs/<clean> --custom-run private/runs/<custom>
```

Direct check, without the corpus:

```
clean   fonts: Carlito, NotoSerif-Regular
custom  fonts: Carlito, Gelasio-Regular
```

Acceptance: `georgia` moves from `T1` to `PASS`, and nothing else degrades.

## Revert

Nothing is patched in place. Unset `CUSTOM_IMAGE` and the harness uses the
clean image again.

## Caveats

- The file fetched is a **variable font** (`Gelasio[wght].ttf`). LibreOffice
  handled it here, but a static instance is the safer long-term choice.
- This fixes the *substitution*, not the underlying brittleness: a document
  using a font nobody has will still drift. See `docs/AUTHORING.md`.
