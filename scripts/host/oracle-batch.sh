#!/usr/bin/env bash
# Render a directory of documents through the Windows oracle VM.
#
#   oracle-batch.sh IN_DIR OUT_DIR [DOMAIN]
#
# IN_DIR must contain one directory per job:
#   <jobid>/document.docx
#
# Results land in OUT_DIR/<jobid>/ with document.pdf, result.json and a
# DONE/FAIL marker, plus agent.log and status.json for provenance.
#
# The whole render happens with the guest offline: the disk is populated while
# the VM is stopped, the VM boots with no NIC, and the agent shuts it down when
# the queue drains. Completion is the domain reaching "shut off".
set -euo pipefail

IN=${1:?usage: oracle-batch.sh IN_DIR OUT_DIR [DOMAIN]}
OUT=${2:?usage: oracle-batch.sh IN_DIR OUT_DIR [DOMAIN]}
DOMAIN=${3:-${ORACLE_DOMAIN:-win11-0}}
DISK=${ORACLE_DISK:-/opt/local/win11-0/win11-0_disk0.qcow2}
MOUNT=${ORACLE_MOUNT:-/mnt/os}
BOOT_TIMEOUT=${ORACLE_BOOT_TIMEOUT:-600}
PART=${ORACLE_PART:-/dev/nbd0p3}

log() { printf '%s  %s\n' "$(date -u +%H:%M:%S)" "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

sudo -n true 2>/dev/null || die "passwordless sudo required"

connected=0
mounted=0
cleanup() {
  if [ "$mounted" = 1 ]; then sudo -n umount "$MOUNT" 2>/dev/null || true; fi
  if [ "$connected" = 1 ]; then sudo -n qemu-nbd --disconnect /dev/nbd0 >/dev/null 2>&1 || true; fi
}
trap cleanup EXIT

domstate() { sudo -n virsh domstate "$DOMAIN" 2>/dev/null || echo "unknown"; }

ensure_off() {
  local s; s=$(domstate)
  if [ "$s" = "shut off" ] || [ "$s" = "unknown" ]; then return 0; fi
  log "shutting down $DOMAIN"
  sudo -n virsh shutdown "$DOMAIN" >/dev/null || die "shutdown failed"
  for _ in $(seq 1 180); do
    [ "$(domstate)" = "shut off" ] && return 0
    sleep 1
  done
  die "domain did not shut down"
}

attach() {  # $1 = ro|rw
  sudo -n modprobe nbd max_part=16
  sudo -n mkdir -p "$MOUNT"
  if [ "$1" = "ro" ]; then
    sudo -n qemu-nbd --connect=/dev/nbd0 -r "$DISK"
  else
    sudo -n qemu-nbd --connect=/dev/nbd0 "$DISK"
  fi
  connected=1
  for _ in $(seq 1 20); do [ -b "$PART" ] && break; sleep 1; done
  [ -b "$PART" ] || die "partition $PART never appeared"
  if [ "$1" = "ro" ]; then
    sudo -n ntfs-3g -o ro "$PART" "$MOUNT"
  else
    sudo -n ntfs-3g "$PART" "$MOUNT"
  fi
  mounted=1
}

detach() {
  sync
  sudo -n umount "$MOUNT"; mounted=0
  sudo -n qemu-nbd --disconnect /dev/nbd0 >/dev/null; connected=0
}

# ---- stage -----------------------------------------------------------------
ensure_off
attach rw

log "staging $(find "$IN" -maxdepth 1 -mindepth 1 -type d | wc -l) job(s)"
sudo -n rm -rf "$MOUNT/work/in" "$MOUNT/work/out"
sudo -n mkdir -p "$MOUNT/work/in" "$MOUNT/work/out"
for job in "$IN"/*/; do
  [ -f "${job}document.docx" ] || continue
  name=$(basename "$job")
  sudo -n mkdir -p "$MOUNT/work/in/$name"
  sudo -n cp "${job}document.docx" "$MOUNT/work/in/$name/document.docx"
done
sudo -n rm -f "$MOUNT/work/agent/agent.log"
detach

# ---- run -------------------------------------------------------------------
log "booting $DOMAIN"
sudo -n virsh start "$DOMAIN" >/dev/null || die "start failed"
deadline=$(( $(date +%s) + BOOT_TIMEOUT ))
while :; do
  if [ "$(domstate)" = "shut off" ]; then
    log "oracle finished and powered off"
    break
  fi
  [ "$(date +%s)" -ge "$deadline" ] && die "timed out after ${BOOT_TIMEOUT}s"
  sleep 3
done

# ---- collect ---------------------------------------------------------------
attach ro
mkdir -p "$OUT"
sudo -n cp -r "$MOUNT/work/out/." "$OUT"/
sudo -n cp "$MOUNT/work/agent/agent.log" "$OUT/agent.log" 2>/dev/null || true
sudo -n cp "$MOUNT/work/agent/status.json" "$OUT/status.json" 2>/dev/null || true
detach

done_n=$(find "$OUT" -name DONE | wc -l)
fail_n=$(find "$OUT" -name FAIL | wc -l)
log "collected: $done_n ok, $fail_n failed"
[ "$fail_n" -eq 0 ] || exit 3
