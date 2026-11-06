"""Harvest documents linked from a public web page.

Given a page that lists forms or documents, follow the links to .doc/.docx
files and record full provenance: the page it was found on, the file URL, and
the hash. Provenance is the point — an unattributed document cannot be used in
a published corpus.
"""

from __future__ import annotations

import hashlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UA = "ooxml-fidelity-lab/0.1 (+https://github.com/rborso/ooxml-fidelity-lab)"
TIMEOUT = 45
DOC_EXT = (".docx", ".doc", ".odt")

HREF = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read()


def document_links(page_url: str, limit: int = 200) -> list[str]:
    """Absolute .doc/.docx URLs found on the page, in page order.

    Some government sites answer 403 to anything without a browser fingerprint,
    and some build the list with JavaScript. Both are reported, not raised: a
    page that cannot be harvested is a finding about the page.
    """
    try:
        html = _get(page_url).decode("utf-8", "replace")
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        print(f"  cannot read {page_url}: {exc}")
        return []
    found: list[str] = []
    seen: set[str] = set()
    for href in HREF.findall(html):
        if not href.lower().split("?")[0].endswith(DOC_EXT):
            continue
        absolute = urllib.parse.urljoin(page_url, href)
        if absolute in seen:
            continue
        seen.add(absolute)
        found.append(absolute)
        if len(found) >= limit:
            break
    return found


def _safe(name: str) -> str:
    name = urllib.parse.unquote(name)
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-")
    return name or "document"


def harvest(
    page_url: str,
    out_dir: Path,
    prefix: str,
    limit: int = 25,
    delay: float = 0.5,
    verbose: bool = True,
) -> list[dict]:
    """Download documents linked from `page_url`. Returns manifest entries."""
    out_dir.mkdir(parents=True, exist_ok=True)
    links = document_links(page_url, limit=limit)
    if verbose:
        print(f"links found: {len(links)}")

    entries: list[dict] = []
    for url in links:
        name = _safe(Path(urllib.parse.urlparse(url).path).name)
        target = out_dir / f"{prefix}-{name}"
        if not target.suffix.lower() in DOC_EXT:
            continue

        if target.exists() and target.stat().st_size > 0:
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            entries.append(_entry(target, digest, url, page_url, prefix))
            if verbose:
                print(f"  kept {target.name} (already present)")
            continue

        try:
            data = _get(url)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
            if verbose:
                print(f"  failed {name}: {exc}")
            continue
        finally:
            time.sleep(delay)

        if len(data) < 1024:
            if verbose:
                print(f"  skipped {name}: {len(data)} bytes is not a document")
            continue

        target.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        entries.append(_entry(target, digest, url, page_url, prefix))
        if verbose:
            print(f"  got {target.name} ({len(data) // 1024} KiB)")

    return entries


def _entry(target: Path, digest: str, url: str, page_url: str, prefix: str) -> dict:
    # The file name already carries the prefix, so the id is the stem; adding
    # the prefix again would produce hu-oif-hu-oif-...
    return {
        "id": target.stem,
        "sha256": digest,
        "path": str(target),
        "class": "case_document",
        "source": prefix,
        "authored_in": "unknown",
        "tags": [prefix, "web-harvest"],
        "licence": "unknown-upstream",
        "split": "dev",
        "source_url": url,
        "found_on": page_url,
        "notes": f"harvested from {urllib.parse.urlparse(page_url).netloc}",
    }
