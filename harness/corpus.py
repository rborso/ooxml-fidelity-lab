"""Corpus manifest loading and validation."""

from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REQUIRED = ("id", "path", "class", "source", "split")


@dataclass
class Item:
    id: str
    path: Path
    cls: str
    source: str
    split: str
    sha256: str | None = None
    tags: list[str] = field(default_factory=list)
    licence: str | None = None

    @property
    def exists(self) -> bool:
        return self.path.exists()

    def actual_sha256(self) -> str | None:
        if not self.exists:
            return None
        h = hashlib.sha256()
        with open(self.path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()


def load(manifest: Path) -> tuple[int, list[Item]]:
    data = yaml.safe_load(manifest.read_text()) or {}
    base = manifest.parent
    items: list[Item] = []
    seen: set[str] = set()

    for raw in data.get("items") or []:
        missing = [k for k in REQUIRED if not raw.get(k)]
        if missing:
            raise ValueError(f"item {raw.get('id', '?')} missing {missing}")
        if raw["id"] in seen:
            raise ValueError(f"duplicate id {raw['id']}")
        seen.add(raw["id"])
        items.append(
            Item(
                id=raw["id"],
                path=(base / raw["path"]).resolve(),
                cls=raw["class"],
                source=raw["source"],
                split=raw["split"],
                sha256=raw.get("sha256"),
                tags=list(raw.get("tags") or []),
                licence=raw.get("licence"),
            )
        )
    return int(data.get("corpus_version", 0)), items


def validate(manifest: Path, verbose: bool = True) -> int:
    """Return a process exit code. Warnings do not fail the check."""
    version, items = load(manifest)
    problems = 0
    if verbose:
        print(f"corpus_version={version} items={len(items)}")
    for item in items:
        if not item.exists:
            print(f"  MISSING FILE  {item.id}: {item.path}", file=sys.stderr)
            problems += 1
            continue
        if item.sha256 and item.sha256 != "0" * 64:
            actual = item.actual_sha256()
            if actual != item.sha256:
                print(f"  HASH MISMATCH {item.id}: {actual}", file=sys.stderr)
                problems += 1
        if not item.licence:
            print(f"  NO LICENCE    {item.id}", file=sys.stderr)
    if verbose:
        print(f"problems={problems}")
    return 0 if problems == 0 else 1
