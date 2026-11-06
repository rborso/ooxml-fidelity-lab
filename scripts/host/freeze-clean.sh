#!/usr/bin/env bash
# Freeze the clean build. Run once, immediately after a successful build.
#
#   freeze-clean.sh
#
# The build tree is what makes a patch take 15 seconds instead of three hours,
# and the clean snapshot is the A/B baseline. Both are mutable: a reconfigure,
# a pull, or a stray make clean destroys them silently. This archives the
# snapshot as an immutable artifact and records what produced it.
set -euo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
BUILD=$REPO/build
SRC=$BUILD/core
OUT=$REPO/private/build
LOG=$REPO/private/build/timing.log

cd "$SRC"
REV=$(git rev-parse HEAD)
BRANCH=$(git rev-parse --abbrev-ref HEAD)
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
TAR=$BUILD/instdir-clean-$STAMP.tar.gz

[ -f "$SRC/instdir/program/.build-ok" ] || { echo "no .build-ok: nothing to freeze" >&2; exit 1; }
[ -d "$BUILD/instdir-clean" ] || { echo "no instdir-clean: run snapshot-clean first" >&2; exit 1; }

echo "archiving $(du -sh "$BUILD/instdir-clean" | cut -f1) to $(basename "$TAR")"
tar -C "$BUILD" -czf "$TAR" instdir-clean

SHA=$(sha256sum "$TAR" | cut -d' ' -f1)
VER=$("$BUILD/instdir-clean/program/soffice" --version 2>/dev/null | head -1)
FILES=$(find "$BUILD/instdir-clean" -type f | wc -l)

cat > "$OUT/clean-baseline.yaml" <<EOF
# Immutable record of the build that produced instdir-clean.
# Never edit. A new baseline means a new file, not an updated one.
built_at: $STAMP
branch: $BRANCH
commit: $REV
version: "$VER"
source_tree: $SRC
snapshot: build/instdir-clean
archive: build/$(basename "$TAR")
archive_sha256: $SHA
archive_bytes: $(stat -c%s "$TAR")
instdir_files: $FILES
configure_flags: |
$(sed -n '/^CONFIGURE_FLAGS=/,/}/p' "$REPO/scripts/host/build-timed.sh" | sed 's/^/  /')
timings:
$(grep -E '_seconds=' "$LOG" | tail -6 | sed 's/^/  /')
EOF

echo "wrote $OUT/clean-baseline.yaml"
echo "sha256 $SHA"
