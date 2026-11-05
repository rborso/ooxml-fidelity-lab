"""Tiered comparison of two layout trees.

T0 is content. It runs first and short-circuits everything: a geometry report on
a document that lost a table is worse than useless.
"""

from __future__ import annotations

import statistics

from .extract import line_signature, page_text


def _t0(reference: dict, candidate: dict) -> dict:
    """Same words, same order, same page."""
    issues: list[str] = []
    if len(reference["pages"]) != len(candidate["pages"]):
        issues.append(
            f"page count {len(candidate['pages'])} != {len(reference['pages'])}"
        )

    for rp, cp in zip(reference["pages"], candidate["pages"]):
        rt, ct = page_text(rp), page_text(cp)
        if rt == ct:
            continue
        if len(rt) != len(ct):
            issues.append(
                f"page {rp['number']}: {len(ct)} words != {len(rt)}"
            )
            continue
        for i, (a, b) in enumerate(zip(rt, ct)):
            if a != b:
                issues.append(
                    f"page {rp['number']} word {i}: {b!r} != {a!r}"
                )
                break

    return {"pass": not issues, "issues": issues[:10]}


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

    return {
        "median_pt": round(statistics.median(deltas), 3) if deltas else 0.0,
        "p95_pt": round(sorted(deltas)[int(len(deltas) * 0.95)], 3) if deltas else 0.0,
        "deltas": len(deltas),
        "fonts_missing": fonts_missing,
        "fonts_extra": fonts_extra,
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

    if not t1["pass"]:
        tier, score = "T1", 0.25
    elif t2["median_pt"] > median_max or t2["p95_pt"] > p95_max:
        tier, score = "T2", 0.75
    elif t2["fonts_missing"] or t2["fonts_extra"]:
        tier, score = "T2-fonts", 0.9
    else:
        tier, score = "PASS", 1.0

    return {"t0": t0, "t1": t1, "t2": t2, "score": score, "tier": tier}
