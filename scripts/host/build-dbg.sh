#!/usr/bin/env bash
# Build a second, instrumented tree.
#
#   build-dbg.sh
#
# The baseline tree is built without --enable-dbgutil, so SAL_INFO and SAL_WARN
# are compiled out and `SAL_LOG=+writerfilter` prints nothing. Every diagnosis in
# this project has therefore been done blind, by property changes and page
# counts. This tree exists so a trace can be read instead.
#
# It is deliberately separate: the clean and patched builds that the corpus is
# measured against must stay exactly as they are, and a debug build has
# different assertions and layout. Nothing here is used for a score.
set -euo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
ROOT=$REPO/build-dbg
SRC=$ROOT/core
BRANCH=libreoffice-26-2
LOG=$REPO/private/build/dbg-build.log

mkdir -p "$ROOT" "$REPO/private/build"
log() { printf '%s  %s\n' "$(date -Is)" "$*" | tee -a "$LOG" >&2; }

if [ ! -d "$SRC/.git" ]; then
  log "cloning $BRANCH (shallow)"
  git clone --depth 1 --branch "$BRANCH" https://github.com/LibreOffice/core "$SRC" >>"$LOG" 2>&1
fi
cd "$SRC"

if [ ! -f config_host.mk ]; then
  log "configuring with --enable-dbgutil"
  ./autogen.sh \
    --enable-dbgutil --enable-ccache --with-lang=en-US --without-java \
    --disable-odk --without-help --without-myspell-dicts \
    --disable-dependency-tracking --disable-scripting-beanshell \
    --disable-scripting-javascript --disable-gstreamer-1-0 --with-galleries=no \
    >>"$LOG" 2>&1 || { log "FAIL configure"; exit 1; }
fi

log "building (this is the long one)"
start=$(date +%s)
if make -j"$(nproc)" >>"$LOG" 2>&1; then
  log "done build seconds=$(( $(date +%s) - start ))"
  touch "$SRC/instdir/program/.build-ok"
else
  log "FAIL build seconds=$(( $(date +%s) - start ))"
  exit 1
fi
