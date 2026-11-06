#!/usr/bin/env bash
# Apply one patch to a LibreOffice source tree and rebuild.
#
#   build-custom.sh <patch-dir> [--configure]
#
# Requires LO_SRC to point at an existing checkout. Nothing is cloned here.
# The first build in a tree is expensive; every later one touches only what the
# patch changed, so iteration is cheap once the tree exists.
set -euo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
PATCH_DIR=${1:?usage: build-custom.sh PATCH_DIR [--configure]}
LO_SRC=${LO_SRC:?set LO_SRC to the LibreOffice source checkout}
LO_BUILD=${LO_BUILD:-$REPO/build}
CONFIGURE=${2:-}

[ -d "$LO_SRC/.git" ] || { echo "LO_SRC is not a git checkout: $LO_SRC" >&2; exit 1; }
PATCH_FILE="$PATCH_DIR/fix.patch"
[ -f "$PATCH_FILE" ] || { echo "no fix.patch in $PATCH_DIR" >&2; exit 1; }

cd "$LO_SRC"
echo "== applying $PATCH_FILE =="
if git apply --check "$PATCH_FILE" 2>/dev/null; then
  git apply "$PATCH_FILE"
elif git apply --reverse --check "$PATCH_FILE" 2>/dev/null; then
  echo "patch already applied; continuing"
else
  echo "patch does not apply cleanly; resolve by hand" >&2
  exit 1
fi

if [ "$CONFIGURE" = "--configure" ] || [ ! -f Makefile ]; then
  echo "== autogen =="
  ./autogen.sh --enable-ccache --with-lang=en-US --without-java --disable-dependency-tracking
fi

echo "== build =="
make -j"$(nproc)"

SOFFICE="$LO_SRC/instdir/program/soffice"
[ -x "$SOFFICE" ] || { echo "build produced no $SOFFICE" >&2; exit 1; }

mkdir -p "$LO_BUILD"
ln -sfn "$SOFFICE" "$LO_BUILD/soffice"
echo
echo "custom renderer ready:"
echo "  export CUSTOM_SOFFICE=$LO_BUILD/soffice"
