#!/usr/bin/env bash
# Rebuild after a configure change, once the host is idle.
#
#   rebuild.sh
#
# Waits for any running measurement, discards the previous snapshot (it may be
# from a failed build), reconfigures, rebuilds, and snapshots only on success.
set -euo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
BUILD=$REPO/build
LOG=$REPO/private/build/timing.log

log() { printf '%s  %s\n' "$(date -Is)" "$*" | tee -a "$LOG" >&2; }

log "rebuild queued; waiting for the host to be idle"
while pgrep -f "promote_known_good" >/dev/null 2>&1 \
   || pgrep -f "make -j" >/dev/null 2>&1; do
  sleep 15
done

# The previous snapshot came from a failed build. It is not a baseline.
if [ -d "$BUILD/instdir-clean" ]; then
  log "discarding previous instdir-clean (failed build)"
  rm -rf "$BUILD/instdir-clean"
fi

log "reconfiguring without --disable-avmedia"
"$REPO/scripts/host/build-timed.sh" configure
log "building"
"$REPO/scripts/host/build-timed.sh" build
log "snapshotting the clean tree"
"$REPO/scripts/host/build-timed.sh" snapshot-clean
log "rebuild complete"
