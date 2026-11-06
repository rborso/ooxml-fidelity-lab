#!/usr/bin/env python3
"""Promote candidate documents that actually pass into known-good controls.

A document is only known-good if it was measured and scored PASS. Anything that
fails stays a candidate and is reported: a control that fails before any patch
exists is worse than no control, because it teaches you to ignore failures.

Waits for the compiler and the post-build chain to finish first: a loaded host
can push a render past the agent's watchdog and manufacture a failure.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
PY = REPO / ".venv" / "bin" / "python"
SIDECAR = REPO / "private" / "corpus" / "known-good.yaml"


def wait_for_quiet(timeout_s: int = 6 * 3600) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        busy = subprocess.run(
            ["pgrep", "-f", "make -j"], capture_output=True
        ).returncode == 0
        chain = subprocess.run(
            ["pgrep", "-f", "post-build.sh"], capture_output=True
        ).returncode == 0
        if not busy and not chain:
            return
        time.sleep(15)
    raise SystemExit("host never went quiet")


def candidates() -> list[dict]:
    data = yaml.safe_load(SIDECAR.read_text())
    return [i for i in data["items"] if i.get("class") == "candidate_known_good"]


def main() -> int:
    print("waiting for the host to be idle", flush=True)
    wait_for_quiet()

    items = candidates()
    if not items:
        print("no candidates to measure")
        return 0
    print(f"measuring {len(items)} candidates", flush=True)

    ids = ",".join(i["id"] for i in items)
    run = subprocess.run(
        [
            str(PY), "-m", "harness.cli", "run",
            "--oracle", "windows",
            "--corpus", "private/corpus/manifest.yaml",
            "--only", ids,
            "--out", "private/runs",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    print(run.stdout[-3000:])
    if run.returncode != 0:
        print(run.stderr[-2000:], file=sys.stderr)
        return 1

    runs = sorted((REPO / "private" / "runs").glob("run-*"), key=lambda p: p.stat().st_mtime)
    results = json.loads((runs[-1] / "results.json").read_text())
    tiers = {d["id"]: d["tier"] for d in results["documents"]}

    data = yaml.safe_load(SIDECAR.read_text())
    promoted, kept, failed = 0, 0, []
    for item in data["items"]:
        tier = tiers.get(item["id"])
        if tier is None:
            continue
        if tier == "PASS":
            item["class"] = "known_good"
            tags = set(item.get("tags") or [])
            tags.discard("candidate")
            tags.add("known-good")
            tags.add("measured-pass")
            item["tags"] = sorted(tags)
            promoted += 1
        else:
            item["class"] = "candidate_known_good"
            tags = set(item.get("tags") or [])
            tags.add("measured-" + tier.lower())
            item["tags"] = sorted(tags)
            kept += 1
            failed.append((item["id"], tier))

    SIDECAR.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))

    total_good = sum(1 for i in data["items"] if i.get("class") == "known_good")
    print(f"\npromoted={promoted} still-candidate={kept} total_known_good={total_good}")
    if failed:
        print("did not pass:")
        for doc_id, tier in failed:
            print(f"  {doc_id:40s} {tier}")
    print(f"run: {runs[-1].name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
