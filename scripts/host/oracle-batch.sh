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
n_jobs=0
for job in "$IN"/*/; do
  # Any document.*, not just .docx: legacy .doc is part of the corpus and
  # cannot be renamed to .docx without Word parsing it as OOXML.
  src=$(find "${job}" -maxdepth 1 -type f -name 'document.*' | head -1)
  [ -n "$src" ] || continue
  name=$(basename "$job")
  sudo -n mkdir -p "$MOUNT/work/in/$name"
  sudo -n cp "$src" "$MOUNT/work/in/$name/$(basename "$src")"
  n_jobs=$((n_jobs + 1))
done
sudo -n rm -f "$MOUNT/work/agent/agent.log"
detach

# ---- run -------------------------------------------------------------------
# BOOT_TIMEOUT covers boot only. Word needs time per document, and the guest is
# offline so there is no signal between "booted" and "powered off"; the deadline
# has to assume the worst case for every job or a large corpus reads as a hang.
PER_DOC=${ORACLE_PER_DOC:-30}
# The guest writes a PDF and a marker per finished job. If the block device
# stops accumulating written bytes while the domain is still running, nothing is
# completing - so that, not the deadline, is the real stall signal. Both are
# host-side: the guest stays offline and nothing in the image changes.
STALL_SECS=${ORACLE_STALL_SECS:-300}
limit=$(( BOOT_TIMEOUT + PER_DOC * n_jobs ))
log "booting $DOMAIN ($n_jobs jobs, ${limit}s limit, ${STALL_SECS}s stall limit)"
sudo -n virsh start "$DOMAIN" >/dev/null || die "start failed"
deadline=$(( $(date +%s) + limit ))
last_wr=-1; last_cpu=-1; last_change=$(date +%s); last_note=0; have_block=0
while :; do
  now=$(date +%s)
  if [ "$(domstate)" = "shut off" ]; then
    log "oracle finished and powered off"
    break
  fi
  [ "$now" -ge "$deadline" ] && die "timed out after ${limit}s for $n_jobs job(s)"

  stats=$(sudo -n virsh domstats "$DOMAIN" --block --vcpu 2>/dev/null || true)
  if printf '%s\n' "$stats" | grep -q 'wr\.bytes='; then have_block=1; fi
  wr=$(printf '%s\n' "$stats" | awk -F= '/\.wr\.bytes=/ {s+=$2} END {printf "%d", s}')
  cpu=$(printf '%s\n' "$stats" | awk -F= '/vcpu\.[0-9]+\.time=/ {s+=$2} END {printf "%d", s}')
  # Block writes are the honest signal: a PDF per document. Fall back to vCPU
  # time only if this libvirt does not expose block stats at all.
  if [ "$have_block" = 1 ]; then signal=$wr; else signal=$cpu; fi
  if [ "$signal" != "${last_signal:-}" ]; then
    last_signal=$signal; last_change=$now
  fi
  idle=$(( now - last_change ))

  if [ $(( now - last_note )) -ge 300 ]; then
    log "progress: ${wr} bytes written, ${cpu}s cpu, ${idle}s since last write"
    last_note=$now
  fi
  if [ "$idle" -ge "$STALL_SECS" ]; then
    die "stalled: no guest activity for ${idle}s (${wr} bytes written, ${cpu}s cpu, domain still running)"
  fi
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
