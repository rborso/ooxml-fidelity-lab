#!/usr/bin/env bash
# One patch, one measurement cycle, in the only correct order.
#
#   batch.sh <patch-dir>
#
# Build first, then measure both builds, then judge. No step is optional: a
# patch that is not measured against a clean run cannot be judged, and a custom
# run without a build has nothing to measure.
#
# The caller must hold the lab lock (make batch does).
set -euo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$REPO"
PATCH_DIR=${1:?usage: batch.sh PATCH_DIR}
PY=.venv/bin/python
CORPUS=${CORPUS:-private/corpus/manifest.yaml}

echo "== 1. build =="
scripts/host/build-custom.sh "$PATCH_DIR"
export CUSTOM_SOFFICE="${CUSTOM_SOFFICE:-$REPO/build/soffice}"

echo "== 2. clean run =="
$PY -m harness.cli run --oracle windows --renderer clean --corpus "$CORPUS" --out private/runs
CLEAN=$(ls -dt private/runs/run-* | head -1)
echo "clean: $CLEAN"

echo "== 3. custom run =="
$PY -m harness.cli run --oracle windows --renderer custom --corpus "$CORPUS" --out private/runs
CUSTOM=$(ls -dt private/runs/run-* | head -1)
echo "custom: $CUSTOM"

echo "== 4. validate =="
$PY -m harness.cli validate --clean-run "$CLEAN" --custom-run "$CUSTOM"
STATUS=$?

echo
echo "clean  $CLEAN"
echo "custom $CUSTOM"
exit $STATUS
