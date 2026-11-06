#!/usr/bin/env bash
# One-time calibration: is our built engine the same engine that gets deployed?
#
#   skew.sh
#
# Renders the whole corpus twice - once with the pinned container image (the
# deployment reference) and once with the unpatched binary from the build tree -
# then measures the difference. Fonts are equalised first, otherwise this
# measures font packaging rather than engine behaviour.
#
# Run this once, and again only when the image digest or the configure flags
# change. It answers a credibility question, not a per-patch one.
set -euo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
PY=$REPO/.venv/bin/python
CORPUS=${CORPUS:-private/corpus/public}
GELASIO=$REPO/patches/0002-gelasio-font/fonts
FONTS=$REPO/private/fonts/container
CONF=$REPO/private/fonts/fonts.conf

say() { printf '\n== %s\n' "$*"; }

say "fonts: mirror the container bundle"
mkdir -p "$FONTS"
if [ ! -f "$FONTS/.extracted" ]; then
  img=$("$PY" -c 'from harness import render; print(render.COLLABORA_IMAGE)')
  tarball=$REPO/private/fonts/image.tar
  if [ ! -f "$tarball" ]; then
    # Exporting the rootfs is the only reliable route: the image has no shell,
    # and extracting everything leaves root-owned files a normal user cannot
    # remove. Extract only the font files out of the tar instead.
    podman create --name skew-fonts "$img" >/dev/null
    podman export skew-fonts > "$tarball"
    podman rm -f skew-fonts >/dev/null
  fi
  tar -xf "$tarball" -C "$FONTS" --strip-components=5 \
      --wildcards '*share/fonts/truetype/*.ttf' 2>/dev/null || true
  [ -d "$GELASIO" ] && cp -n "$GELASIO"/*.ttf "$FONTS/" 2>/dev/null || true
  touch "$FONTS/.extracted"
fi
echo "font files: $(ls "$FONTS"/*.ttf 2>/dev/null | wc -l)"

cat > "$CONF" <<EOF
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <dir>$FONTS</dir>
  <cachedir>/tmp/ooxml-fontcache</cachedir>
</fontconfig>
EOF

say "run 1/2: pinned image (deployment reference)"
ref_out=$("$PY" -m harness.cli run --oracle windows --renderer image \
  --corpus "$CORPUS" --out private/runs)
echo "$ref_out" | tail -3
REF="private/runs/$(echo "$ref_out" | sed -n 's/^run: //p' | tail -1)"

say "run 2/2: built-clean, same fonts"
new_out=$(CLEAN_SOFFICE=${CLEAN_SOFFICE:-$REPO/build/instdir-clean/program/soffice} \
LO_FONTCONFIG=$CONF \
"$PY" -m harness.cli run --oracle windows --renderer built-clean \
  --corpus "$CORPUS" --out private/runs)
echo "$new_out" | tail -3
NEW="private/runs/$(echo "$new_out" | sed -n 's/^run: //p' | tail -1)"

say "skew"
"$PY" -m harness.cli validate --clean-run "$REF" --custom-run "$NEW" || true
echo "reference run: $REF"
echo "built run:     $NEW"
