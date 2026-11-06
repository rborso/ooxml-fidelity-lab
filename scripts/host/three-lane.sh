#!/usr/bin/env bash
# Three lanes against one Word baseline.
#
#   three-lane.sh [REF_RUN]
#
#   upstream      the pinned container image: what gets deployed
#   built-clean   the unpatched binary from the build tree
#   built-custom  the same tree plus the patch under test
#
# All three reuse one set of reference PDFs. Comparing two renderers against two
# separate oracle passes would fold oracle variance into the difference, which is
# the one thing this project cannot afford.
set -euo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
PY=$REPO/.venv/bin/python
CORPUS=${CORPUS:-private/corpus/manifest.yaml}
CLEAN=${CLEAN_SOFFICE:-$REPO/build/instdir-clean/program/soffice}
CUSTOM=${CUSTOM_SOFFICE:-$REPO/build/instdir-custom/program/soffice}
FONTS=$REPO/private/fonts/fonts.conf
cd "$REPO"

REF=${1:-$(ls -dt private/runs/run-* | head -20 | while read -r d; do
  [ "$(find "$d/ref" -name '*.pdf' 2>/dev/null | wc -l)" -ge 300 ] && { echo "$d"; break; }
done)}
[ -n "$REF" ] || { echo "no run with reference PDFs found" >&2; exit 1; }

export PYTHONUNBUFFERED=1
say() { printf "\n== %s\n" "$*" >&2; }

lane() {  # name renderer [binary]
  local name=$1 renderer=$2 binary=${3:-}
  say "lane: $name ($renderer ${binary:+$binary})"
  if [ -n "$binary" ]; then
    env CLEAN_SOFFICE="$binary" CUSTOM_SOFFICE="$binary" LO_FONTCONFIG="$FONTS" \
      "$PY" -m harness.cli run --reuse-ref "$REF" --renderer "$renderer" \
      --corpus "$CORPUS" --out private/runs > "$REPO/private/build/lane-$name.log" 2>&1
  else
    "$PY" -m harness.cli run --reuse-ref "$REF" --renderer "$renderer" \
      --corpus "$CORPUS" --out private/runs > "$REPO/private/build/lane-$name.log" 2>&1
  fi
  # To stderr: stdout carries the run directory only, because callers capture it.
  tail -2 "$REPO/private/build/lane-$name.log" >&2
  ls -dt private/runs/run-* | head -1
}

say "reference: $REF"
UP=$(lane upstream image)
BC=$(lane built-clean built-clean "$CLEAN")
BU=$(lane built-custom built-patched "$CUSTOM")

say "pairwise"
"$PY" -m harness.cli validate --clean-run "$UP" --custom-run "$BC" \
  > private/build/lane-up-vs-builtclean.log 2>&1 || true
"$PY" -m harness.cli validate --clean-run "$BC" --custom-run "$BU" \
  > private/build/lane-builtclean-vs-builtcustom.log 2>&1 || true
tail -1 private/build/lane-up-vs-builtclean.log
tail -1 private/build/lane-builtclean-vs-builtcustom.log

cat > private/build/three-lane.json <<EOF
{"reference": "$REF", "upstream": "$UP", "built_clean": "$BC", "built_custom": "$BU"}
EOF
echo
cat private/build/three-lane.json
