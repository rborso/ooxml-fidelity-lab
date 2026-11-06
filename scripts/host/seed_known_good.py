#!/usr/bin/env python3
"""Generate the candidate known-good documents and register them.

Idempotent: existing ids are left alone, so re-running only adds what is new.
Candidates are *not* known-good until measured and promoted.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from harness import synth_good  # noqa: E402  (needs REPO on the path first)

CORPUS = REPO / "private" / "corpus"
OUT = CORPUS / "public" / "known-good"
SIDECAR = CORPUS / "known-good.yaml"
VARIANTS = 5


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    data = yaml.safe_load(SIDECAR.read_text()) if SIDECAR.exists() else {"items": []}
    existing = {item["id"] for item in data.get("items", [])}

    added = 0
    for construct in synth_good.CONSTRUCTS:
        for seed in range(1, VARIANTS + 1):
            item_id = f"{construct}-{seed}"
            path = synth_good.write(construct, seed, OUT / f"{item_id}.docx")
            if item_id in existing:
                continue
            data["items"].append(
                {
                    "id": item_id,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "path": str(path.relative_to(CORPUS)),
                    "class": "candidate_known_good",
                    "source": "synthetic",
                    "authored_in": "generated",
                    "tags": ["candidate", "known-good-candidate", construct],
                    "licence": "CC0-1.0",
                    "split": "dev",
                    "source_url": (
                        "https://github.com/rborso/ooxml-fidelity-lab/"
                        "blob/main/harness/synth_good.py"
                    ),
                    "notes": f"candidate control, family {construct}",
                }
            )
            added += 1

    SIDECAR.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
    total = len(data["items"])
    good = sum(1 for item in data["items"] if item.get("class") == "known_good")
    pending = sum(1 for item in data["items"] if item.get("class") == "candidate_known_good")
    print(f"added={added} total={total} known_good={good} candidates={pending}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
