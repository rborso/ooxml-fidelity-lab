"""Fetch DOCX attachments from a Bugzilla instance.

Bug-tracker attachments are the cheapest good corpus there is: they are already
minimised by the reporter, already labelled with a failure description, and
they exercise constructs that real users actually hit.

Downloads are recorded with their source URL so provenance survives.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UA = "ooxml-fidelity-lab/0.1 (+https://github.com/rborso/ooxml-fidelity-lab)"
TIMEOUT = 45


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read()


def _get_json(url: str) -> dict:
    return json.loads(_get(url).decode("utf-8", "replace"))


def search(base: str, query: str, limit: int, offset: int = 0) -> list[dict]:
    url = (
        f"{base}/rest/bug?quicksearch={urllib.parse.quote(query)}"
        f"&limit={limit}&offset={offset}&include_fields=id,summary,status,resolution"
    )
    return _get_json(url).get("bugs", [])


def attachments(base: str, bug_id: int) -> list[dict]:
    """Attachment metadata for one bug.

    Bugzilla nests this two ways depending on version: a flat list, or
    {"bugs": {"<id>": [...]}}. Accept both.
    """
    url = f"{base}/rest/bug/{bug_id}/attachment?include_fields=id,file_name,content_type,size,is_obsolete"
    data = _get_json(url)
    if isinstance(data.get("attachments"), list):
        return data["attachments"]
    nested = data.get("bugs") or {}
    if isinstance(nested, dict):
        found = nested.get(str(bug_id)) or []
        return found if isinstance(found, list) else []
    return []


def _safe(name: str, fallback: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name or "").strip("-")
    return name or fallback


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(
    base: str,
    out_dir: Path,
    limit: int = 30,
    query: str = "docx",
    delay: float = 0.4,
    verbose: bool = True,
    pages: int = 1,
) -> list[dict]:
    """Download DOCX attachments and return manifest entries."""
    out_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []
    seen_hashes: set[str] = set()

    bugs: list[dict] = []
    for page in range(max(1, pages)):
        batch = search(base, query, limit * 3, offset=page * limit * 3)
        if not batch:
            break
        bugs.extend(batch)
    if verbose:
        print(f"bugs returned: {len(bugs)}")

    for bug in bugs:
        if len(entries) >= limit:
            break
        try:
            atts = attachments(base, bug["id"])
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError) as exc:
            if verbose:
                print(f"  bug {bug['id']}: cannot list attachments ({exc})")
            continue

        for att in atts:
            if len(entries) >= limit:
                break
            name = att.get("file_name") or ""
            if att.get("is_obsolete"):
                continue
            # Filter by extension only. content_type is unreliable: trackers
            # frequently store DOCX as application/octet-stream.
            if not name.lower().endswith((".docx", ".doc")):
                continue

            url = f"{base}/attachment.cgi?id={att['id']}"
            target = out_dir / f"bug{bug['id']}-{_safe(name, 'attachment.docx')}"
            if not target.suffix.lower() in (".docx", ".doc"):
                target = target.with_suffix(".docx")

            if target.exists() and target.stat().st_size > 0:
                # Already fetched: keep it and its provenance, skip the download.
                digest = _sha256(target)
                if digest in seen_hashes:
                    continue
                seen_hashes.add(digest)
                entries.append(_entry(bug, att, target, digest, url))
                continue

            try:
                data = _get(url)
            except (urllib.error.URLError, urllib.error.HTTPError) as exc:
                if verbose:
                    print(f"  bug {bug['id']} att {att['id']}: download failed ({exc})")
                continue
            finally:
                time.sleep(delay)

            target.write_bytes(data)
            digest = _sha256(target)
            if digest in seen_hashes:
                target.unlink()
                continue
            seen_hashes.add(digest)

            entries.append(_entry(bug, att, target, digest, url))
            if verbose:
                print(f"  got {target.name} ({len(data) // 1024} KiB)  {bug['summary'][:60]}")

    # Merge with a previous fragment so growing the corpus is idempotent.
    previous: list[dict] = []
    fragment_json = out_dir / "manifest-fragment.json"
    if fragment_json.exists():
        try:
            previous = json.loads(fragment_json.read_text())
        except json.JSONDecodeError:
            previous = []
    merged = {entry["id"]: entry for entry in previous}
    for entry in entries:
        merged[entry["id"]] = entry
    entries = sorted(merged.values(), key=lambda e: e["id"])

    fragment_json.write_text(json.dumps(entries, indent=2))
    if verbose:
        print(f"downloaded {len(entries)} document(s) into {out_dir}")
    return entries


def _entry(bug: dict, att: dict, target: Path, digest: str, url: str) -> dict:
    return {
        "id": f"bz{bug['id']}-{att['id']}",
        "sha256": digest,
        "path": f"bugzilla/{target.name}",
        "class": "case_document",
        "source": "bugzilla",
        "authored_in": "unknown",
        "tags": ["bugzilla"],
        "licence": "unknown-upstream",
        # Deterministic split from the content hash: ~19% holdout. Deterministic
        # matters - a random split cannot be reproduced or frozen.
        "split": "holdout" if digest[0] in "012" else "dev",
        "notes": (bug.get("summary") or "")[:160],
        "url": url,
    }


def to_yaml(entries: list[dict]) -> str:
    """Manifest fragment. Provenance is kept: an item without a source URL
    cannot be used in a published corpus."""
    import yaml

    return yaml.safe_dump({"items": entries}, sort_keys=False, allow_unicode=True)
