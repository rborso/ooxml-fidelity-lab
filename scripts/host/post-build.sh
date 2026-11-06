#!/usr/bin/env bash
# Runs once the build finishes: snapshot the clean tree, apply the stand-in
# patch, measure the incremental rebuild, snapshot the custom tree.
#
# Queued in the background so the measurements happen whether or not anyone is
# watching. Aborts if the build produced no binary, so a failed build is not
# snapshotted as if it were good.
set -euo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
SRC=${LO_SRC:-$REPO/build/core}

echo "waiting for the compiler to stop"
while pgrep -f "make -j" >/dev/null 2>&1; do sleep 10; done

if [ ! -x "$SRC/instdir/program/soffice" ]; then
  echo "build produced no $SRC/instdir/program/soffice - not snapshotting" >&2
  exit 1
fi

echo "build artefact present: $("$SRC/instdir/program/soffice" --version 2>/dev/null | head -1)"

"$REPO/scripts/host/build-timed.sh" snapshot-clean
"$REPO/scripts/host/build-timed.sh" stub-patch
"$REPO/scripts/host/build-timed.sh" build-incremental
"$REPO/scripts/host/build-timed.sh" snapshot-custom
"$REPO/scripts/host/build-timed.sh" report
