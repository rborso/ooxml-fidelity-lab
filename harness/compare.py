"""Tiered comparison of two layout trees.

T0 is content. It runs first and short-circuits everything: a geometry report on
a document that lost a table is worse than useless.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter

from .extract import line_signature, page_text

# Substitutions that are metric-compatible by design. If the geometry tier and
# the line breaks already agree, a Calibri->Carlito swap is the desired
# behaviour, not a finding. Anything outside this map is a real substitution.
METRIC_COMPATIBLE: dict[str, set[str]] = {
    "Calibri": {"Carlito"},
    "Cambria": {"Caladea"},
    "Georgia": {"Gelasio"},
    "Arial": {"Liberation Sans", "LiberationSans"},
    "Times New Roman": {"Liberation Serif", "LiberationSerif"},
    "Courier New": {"Liberation Mono", "LiberationMono"},
    "Symbol": {"OpenSymbol", "NotoSansSymbols"},
}

# Word's PDF export names fonts by PostScript name; LibreOffice uses the family.
FONT_ALIASES = {
    "ArialMT": "Arial",
    "Arial-BoldMT": "Arial",
    "Arial-ItalicMT": "Arial",
    "TimesNewRomanPSMT": "Times New Roman",
    "TimesNewRomanPS-BoldMT": "Times New Roman",
    "TimesNewRomanPS-ItalicMT": "Times New Roman",
    "SymbolMT": "Symbol",
    "CourierNewPSMT": "Courier New",
}

# Tokens are compared as alphanumeric runs. Engines differ on whether trailing
# punctuation is its own token ("издания." vs "издания" + "."), which is not a
# content difference.
TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def page_tokens(page: dict) -> list[str]:
    return TOKEN_RE.findall(" ".join(page_text(page)))


def _family(name: str) -> str:
    """'Calibri-Bold' and 'Times New Roman,Bold' both reduce to the family."""
    base = re.split(r"[-,]", name or "")[0].strip()
    return FONT_ALIASES.get(base, base)


def classify_fonts(missing: list[str], extra: list[str]) -> tuple[dict, dict]:
    """Split substitutions into expected (metric-compatible) and unexpected."""
    expected: dict[str, str] = {}
    unexpected: dict[str, str] = {}
    extra_families = [_family(e) for e in extra]
    for want in missing:
        allowed = METRIC_COMPATIBLE.get(_family(want), set())
        hit = next(
            (
                got
                for got, fam in zip(extra, extra_families)
                if any(fam.startswith(a) for a in allowed)
            ),
            None,
        )
        (expected if hit else unexpected)[want] = hit
    return expected, unexpected


def _t0(reference: dict, candidate: dict) -> dict:
    """Content presence first, then content order.

    Losing a word is fatal. Visiting the same words in a different order is a
    reading-order difference: real, worth reporting, but not data loss. Scoring
    it as fatal buries the findings that actually matter.
    """
    content: list[str] = []
    order: list[str] = []

    if len(reference["pages"]) != len(candidate["pages"]):
        content.append(
            f"page count {len(candidate['pages'])} != {len(reference['pages'])}"
        )

    for rp, cp in zip(reference["pages"], candidate["pages"]):
        rt, ct = page_tokens(rp), page_tokens(cp)
        rcount, ccount = Counter(rt), Counter(ct)
        if rcount != ccount:
            missing = rcount - ccount
            extra = ccount - rcount
            bits = []
            if missing:
                names = ", ".join(repr(w) for w in list(missing)[:3])
                bits.append(f"missing {sum(missing.values())} ({names})")
            if extra:
                names = ", ".join(repr(w) for w in list(extra)[:3])
                bits.append(f"extra {sum(extra.values())} ({names})")
            content.append(f"page {rp['number']}: {', '.join(bits)}")
        elif rt != ct:
            first = next(i for i, (a, b) in enumerate(zip(rt, ct)) if a != b)
            order.append(
                f"page {rp['number']} word {first}: {ct[first]!r} != {rt[first]!r}"
            )

    return {
        "pass": not content,
        "content_issues": content[:10],
        "order_issues": order[:10],
        "order_differs": bool(order),
        "issues": (content + order)[:10],
    }


def _t1(reference: dict, candidate: dict) -> dict:
    issues: list[str] = []
    for rp, cp in zip(reference["pages"], candidate["pages"]):
        if rp["line_count"] != cp["line_count"]:
            issues.append(
                f"page {rp['number']}: {cp['line_count']} lines != {rp['line_count']}"
            )
        rs, cs = line_signature(rp), line_signature(cp)
        if rs != cs:
            diff = next(
                (i for i, (a, b) in enumerate(zip(rs, cs)) if a != b), min(len(rs), len(cs))
            )
            got = cs[diff] if diff < len(cs) else "<end>"
            want = rs[diff] if diff < len(rs) else "<end>"
            issues.append(f"page {rp['number']} line {diff} ends {got!r} != {want!r}")
    return {"pass": not issues, "issues": issues[:10]}


def _t2(reference: dict, candidate: dict) -> dict:
    """Per-word bounding-box delta in points, plus font substitutions."""
    deltas: list[float] = []
    for rp, cp in zip(reference["pages"], candidate["pages"]):
        for rw, cw in zip(rp["words"], cp["words"]):
            rcx = (rw["b"][0] + rw["b"][2]) / 2
            rcy = (rw["b"][1] + rw["b"][3]) / 2
            ccx = (cw["b"][0] + cw["b"][2]) / 2
            ccy = (cw["b"][1] + cw["b"][3]) / 2
            deltas.append(max(abs(ccx - rcx), abs(ccy - rcy)))

    fonts_missing = sorted(set(reference["fonts"]) - set(candidate["fonts"]))
    fonts_extra = sorted(set(candidate["fonts"]) - set(reference["fonts"]))
    expected, unexpected = classify_fonts(fonts_missing, fonts_extra)

    return {
        "median_pt": round(statistics.median(deltas), 3) if deltas else 0.0,
        "p95_pt": round(sorted(deltas)[int(len(deltas) * 0.95)], 3) if deltas else 0.0,
        "deltas": len(deltas),
        "fonts_missing": fonts_missing,
        "fonts_extra": fonts_extra,
        "fonts_expected": expected,
        "fonts_unexpected": unexpected,
    }


def compare(reference: dict, candidate: dict, tolerances: dict | None = None) -> dict:
    tol = tolerances or {}
    t2_max = tol.get("t2", {})

    t0 = _t0(reference, candidate)
    if not t0["pass"]:
        return {"t0": t0, "t1": None, "t2": None, "score": 0.0, "tier": "T0"}

    t1 = _t1(reference, candidate)
    t2 = _t2(reference, candidate)

    median_max = float(t2_max.get("median_pt_max", 1.0))
    p95_max = float(t2_max.get("p95_pt_max", 4.0))

    if t0["order_differs"]:
        # Same words, different reading order. Structural tiers are not
        # meaningful on a reordered page, so this tier wins over T1.
        tier, score = "ORDER", 0.5
    elif not t1["pass"]:
        tier, score = "T1", 0.25
    elif t2["median_pt"] > median_max or t2["p95_pt"] > p95_max:
        tier, score = "T2", 0.75
    elif t2["fonts_unexpected"]:
        # A substitution outside the metric-compatible map. Geometry may still
        # be close on this document; it is reported because it will not hold
        # for documents with other content.
        tier, score = "T2-fonts", 0.8
    else:
        # Expected substitutions (or none) with matching layout: a pass.
        tier, score = "PASS", 1.0

    return {"t0": t0, "t1": t1, "t2": t2, "score": score, "tier": tier}
