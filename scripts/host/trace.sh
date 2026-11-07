#!/usr/bin/env bash
# Trace a document through the instrumented tree.
#
#   trace.sh <docx> [area...]
#
# Uses build-dbg, which is configured with --enable-sal-log: SAL_INFO and
# SAL_WARN are active at the release optimisation level. The baseline tree is a
# release build and prints nothing, which is why every earlier diagnosis had to
# rely on page counts and property changes.
set -euo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
DOC=${1:?usage: trace.sh <docx> [area...]}
shift || true
AREAS=${*:-writerfilter}
BIN=$REPO/build-dbg/core/instdir/program/soffice
OUT=$REPO/private/build/trace

[ -x "$BIN" ] || { echo "no instrumented binary at $BIN - run build-dbg.sh" >&2; exit 1; }

mkdir -p "$OUT"
name=$(basename "${DOC%.*}")
log=$OUT/$name.log

echo "areas: +$AREAS" >&2
SAL_LOG="+$AREAS" FONTCONFIG_FILE="$REPO/private/fonts/fonts.conf" \
  "$BIN" --headless --norestore --convert-to pdf --outdir "$OUT" "$DOC" 2> "$log" >/dev/null

echo "trace: $log ($(wc -l < "$log") lines)"
grep -c . "$log" >/dev/null || true
