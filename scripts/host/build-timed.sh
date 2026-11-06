#!/usr/bin/env bash
# Timed, resumable build steps for the custom renderer.
#
#   build-timed.sh <step>
#
# Steps: configure | build | snapshot-clean | stub-patch | build-incremental |
#        snapshot-custom | report
#
# Each step is separate so a failure does not lose the tree, and so the times
# recorded are per phase rather than one opaque number.
set -euo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
SRC=${LO_SRC:-$REPO/build/core}
BUILD=$REPO/build
LOG=$REPO/private/build/timing.log
mkdir -p "$(dirname "$LOG")" "$BUILD"

CONFIGURE_FLAGS=${CONFIGURE_FLAGS:---enable-ccache --with-lang=en-US --without-java \
--disable-odk --without-help --without-myspell-dicts --disable-dependency-tracking \
--disable-scripting-beanshell --disable-scripting-javascript \
--disable-gstreamer-1-0 --with-galleries=no}

log() { printf '%s  %s\n' "$(date -Is)" "$*" | tee -a "$LOG" >&2; }

timed() {  # timed LABEL command...
  local label=$1; shift
  local start end
  start=$(date +%s)
  log "start $label"
  if "$@"; then
    end=$(date +%s)
    log "done  $label seconds=$((end - start))"
    printf '%s_seconds=%s\n' "$label" "$((end - start))" | tee -a "$LOG" >&2
  else
    end=$(date +%s)
    log "FAIL  $label seconds=$((end - start))"
    return 1
  fi
}

step=${1:?usage: build-timed.sh STEP}
cd "$SRC"

case "$step" in
  info)
    log "src=$SRC commit=$(git rev-parse HEAD) branch=$(git rev-parse --abbrev-ref HEAD)"
    du -sh . | tee -a "$LOG"
    nproc | tee -a "$LOG"
    free -g | tee -a "$LOG"
    ;;

  configure)
    # Python 3.12 dropped distutils, and the configure probe that finds the
    # headers still tries to import it. Supply the flags directly instead of
    # depending on that path.
    if command -v python3-config >/dev/null 2>&1; then
      export PYTHON_CFLAGS="$(python3-config --includes)"
      export PYTHON_LIBS="$(python3-config --ldflags --embed)"
      log "python flags: cflags='$PYTHON_CFLAGS' libs='$PYTHON_LIBS'"
    fi
    # COOL builds core with --enable-cp-uno. Probe for it rather than assume:
    # a wrong flag aborts autogen, and the error is easy to misread.
    if ./autogen.sh --help 2>/dev/null | grep -q -- "--enable-cp-uno"; then
      CONFIGURE_FLAGS="$CONFIGURE_FLAGS --enable-cp-uno"
      log "configure: --enable-cp-uno supported, using it"
    else
      log "configure: --enable-cp-uno not present in this revision, using defaults"
    fi
    # shellcheck disable=SC2086
    timed configure ./autogen.sh $CONFIGURE_FLAGS
    ;;

  build)
    timed build make -j"$(nproc)"
    # Success marker. The `soffice` wrapper exists even in a half-built tree,
    # so its presence proves nothing; this file only appears when make exits 0.
    touch "$SRC/instdir/program/.build-ok"
    log "build marker written"
    ;;

  snapshot-clean)
    rm -rf "$BUILD/instdir-clean"
    timed snapshot_clean rsync -a --delete "$SRC/instdir/" "$BUILD/instdir-clean/"
    du -sh "$BUILD/instdir-clean" | tee -a "$LOG"
    ;;

  stub-patch)
    # Stand-in for a real fix: it must compile, and it must touch the module the
    # real patch targets. In 26.2 the writerfilter module was merged into sw, so
    # the path is sw/source/writerfilter/... ; older trees keep it separate.
    f=sw/source/writerfilter/dmapper/SdtHelper.cxx
    [ -f "$f" ] || f=writerfilter/source/dmapper/SdtHelper.cxx
    [ -f "$f" ] || f=$(ls sw/source/writerfilter/dmapper/*.cxx 2>/dev/null | head -1)
    [ -n "${f:-}" ] && [ -f "$f" ] || { log "no writerfilter dmapper source to patch"; exit 1; }
    if ! grep -q "ooxml-fidelity-lab stand-in" "$f"; then
      sed -i '1i // ooxml-fidelity-lab stand-in: measures one incremental rebuild.\n' "$f"
      git diff > "$BUILD/stub.patch"
      log "stub patch written to $BUILD/stub.patch (file: $f)"
    else
      log "stub patch already applied"
    fi
    ;;

  build-incremental)
    timed build_incremental make -j"$(nproc)"
    ;;

  snapshot-custom)
    rm -rf "$BUILD/instdir-custom"
    timed snapshot_custom rsync -a --delete "$SRC/instdir/" "$BUILD/instdir-custom/"
    du -sh "$BUILD/instdir-custom" | tee -a "$LOG"
    ;;

  report)
    echo "--- timing log ---"
    cat "$LOG"
    echo
    echo "clean  binary: $BUILD/instdir-clean/program/soffice"
    echo "custom binary: $BUILD/instdir-custom/program/soffice"
    ;;

  *)
    echo "unknown step: $step" >&2
    exit 1
    ;;
esac
