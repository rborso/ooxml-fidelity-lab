#!/usr/bin/env bash
# Serialise lab work. Builds and measurement runs must never overlap: a compile
# steals cores, and a loaded host can push a document past the agent's watchdog
# and turn a good render into a FAIL.
#
#   lab-lock.sh <name> <command...>
#
# Exit 75 (EX_TEMPFAIL) if another job holds the lock.
set -euo pipefail

LOCK=${LAB_LOCK:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/private/lab.lock}
NAME=${1:?usage: lab-lock.sh NAME COMMAND...}
shift

mkdir -p "$(dirname "$LOCK")"
exec 9>"$LOCK"

if ! flock -n 9; then
  holder=$(cat "${LOCK}.holder" 2>/dev/null || echo "unknown (stale lock?)")
  echo "lab is busy: $holder" >&2
  echo "$NAME refused; nothing was started" >&2
  exit 75
fi

printf '%s pid=%s started=%s\n' "$NAME" "$$" "$(date -Is)" > "${LOCK}.holder"
trap 'rm -f "${LOCK}.holder"' EXIT INT TERM

echo "lab lock held by $NAME"
exec "$@"
