"""Placement checks: geometry that a human would notice by eye.

The tiered comparator reports median and p95 displacement. That is blind to a
localized defect by construction: one table shifted 52 pt among 325 documents
barely moves a percentile, and a whole page pushed outside the margin does not
move it at all.

Three checks, all pure geometry over the extracted layout, none of which needs
Microsoft Word to decide what is correct:

* **outside** - a word or drawing outside the area the reference covers, i.e.
  content the other engine places in the margin or off the page;
* **displaced** - a word matched by text whose horizontal position differs by
  more than a threshold while staying on the same line. This is the check that
  catches one table moving left;
* **clipped** - a word whose box leaves the page rectangle.

Reported as its own axis, like the visual one: it says where to look, not what
the document means.
"""

from __future__ import annotations

# A word moved less than this is layout jitter, not a defect. 30 pt is about
# half a line height and well under one tab stop.
DISPLACED_PT = 30.0
# Only compare words that are on the same visual line.
SAME_ROW_PT = 6.0
# Allowance around the reference content box before "outside" fires. Set to a
# typical page margin: text that lands within a margin's width of the reference
# content is jitter or a wider glyph run, not a misplaced block. Anything
# further out is content the reference never places there.
OUTSIDE_PT = 40.0


def _content_box(words: list[dict]) -> list[float] | None:
    """Box of the words on one page.

    Per page, not per document: a document-wide box makes every page with less
    content than the fullest one look like it has content outside it, and a
    single stray dot above the first word of the busiest page fires.
    """
    if not words:
        return None
    xs = [w["b"][0] for w in words]
    ys = [w["b"][1] for w in words]
    xe = [w["b"][2] for w in words]
    ye = [w["b"][3] for w in words]
    return [min(xs), min(ys), max(xe), max(ye)]


def check(reference: dict, candidate: dict,
          displaced_pt: float = DISPLACED_PT) -> dict:
    """Compare placements. Returns findings, worst-first, per page."""
    findings: list[dict] = []

    for ref_page, cand_page in zip(reference["pages"], candidate["pages"]):
        number = ref_page["number"]
        ref_words = ref_page["words"]
        cand_words = cand_page["words"]

        # outside: a word pushed into the left or right margin. Horizontal only:
        # content at the top or bottom of a page is normal, and a document-wide
        # or per-page box that includes the vertical axis fires on every page
        # with less content than its neighbours.
        ref_box = _content_box(ref_words)
        if ref_box:
            for w in cand_words:
                x0, _y0, x1, _y1 = w["b"]
                if x0 < ref_box[0] - OUTSIDE_PT or x1 > ref_box[2] + OUTSIDE_PT:
                    findings.append({"kind": "outside", "page": number,
                                     "word": w["t"], "box": w["b"]})
                    break   # one per page is enough to make the point

        # displaced: the same word on the same line, moved sideways. Each
        # candidate word may be claimed once, otherwise a repeated word such as
        # "the" pairs with a different instance and every document looks broken.
        free: dict[str, list[dict]] = {}
        for w in cand_words:
            free.setdefault(w["t"], []).append(w)
        for w in ref_words:
            pool = free.get(w["t"]) or []
            best = None
            for other in pool:
                dy = abs(other["b"][1] - w["b"][1])
                if dy >= SAME_ROW_PT:
                    continue
                dx = other["b"][0] - w["b"][0]
                if best is None or abs(dx) < abs(best[0]):
                    best = (dx, other)
            if best is None:
                continue
            pool.remove(best[1])
            if abs(best[0]) > displaced_pt:
                findings.append({"kind": "displaced", "page": number,
                                 "word": w["t"], "dx": round(best[0], 1),
                                 "ref_box": w["b"], "cand_box": best[1]["b"]})

        # clipped: a box that leaves the page
        for w in cand_words:
            x0, y0, x1, y1 = w["b"]
            if x0 < -1 or y0 < -1:
                findings.append({"kind": "clipped", "page": number,
                                 "word": w["t"], "box": w["b"]})
                break

    kinds: dict[str, int] = {}
    for f in findings:
        kinds[f["kind"]] = kinds.get(f["kind"], 0) + 1
    return {
        "findings": findings[:20],
        "count": len(findings),
        "kinds": kinds,
        "severity": "breaking" if kinds.get("outside") or kinds.get("clipped") else (
            "visible" if kinds.get("displaced") else "none"),
    }
