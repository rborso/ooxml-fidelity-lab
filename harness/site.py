"""Build a static, human-readable report site from runs and family records.

No framework, no JavaScript, no build step beyond this file. The output is a
handful of HTML pages written into a directory an HTTP server can hand out.

Sources:
    private/runs/run-*/results.json   measured runs
    docs/families/*.md                failure families (status, fix, retest)
"""

from __future__ import annotations

import html
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

try:  # optional, falls back to <pre>
    import markdown as _md
except ImportError:  # pragma: no cover
    _md = None

from . import pixels

TIER_CLASS = {
    "PASS": "ok",
    "T2-fonts": "warn",
    "T2": "warn",
    "ORDER": "warn",
    "FLOW": "warn",
    "FIELD": "warn",
    "SEGMENT": "warn",
    "T1": "bad",
    "T0": "fatal",
    "ORACLE-FAIL": "fatal",
}

CSS = """
:root{--bg:#fbfbfa;--fg:#1c1c1e;--mut:#6b6b70;--line:#e3e3e0;--ok:#0a7d40;
--warn:#9a6700;--bad:#b3541e;--fatal:#b42318;--card:#fff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
header{border-bottom:1px solid var(--line);background:var(--card)}
header .in,main{max-width:1040px;margin:0 auto;padding:0 24px}
header .in{padding-top:18px;padding-bottom:14px;display:flex;gap:24px;align-items:baseline;
flex-wrap:wrap}
h1{font-size:19px;margin:0;letter-spacing:-.01em}
nav a{margin-right:16px;color:var(--mut);text-decoration:none;font-size:14px}
nav a.on{color:var(--fg);font-weight:600}
main{padding-top:26px;padding-bottom:60px}
h2{font-size:15px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut);
margin:34px 0 10px;font-weight:600}
.cards{display:flex;gap:12px;flex-wrap:wrap}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;
padding:14px 16px;min-width:132px}
.card .n{font-size:26px;font-weight:600;letter-spacing:-.02em}
.card .l{font-size:12px;color:var(--mut);text-transform:uppercase;letter-spacing:.06em}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);
border-radius:8px;overflow:hidden;font-size:14px}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--line)}
th{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--mut);
background:#f6f6f4;font-weight:600}
tr:last-child td{border-bottom:none}
td.num{font-variant-numeric:tabular-nums;text-align:right}
code,.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12.5px}
.mut{color:var(--mut)}
.badge{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;
font-weight:600;border:1px solid}
.badge.ok{color:var(--ok);border-color:#bfe3cd;background:#eefaf2}
.badge.warn{color:var(--warn);border-color:#f0dca8;background:#fdf6e3}
.badge.bad{color:var(--bad);border-color:#f3cbb6;background:#fdf0e9}
.badge.fatal{color:var(--fatal);border-color:#f6c2bd;background:#fdecea}
.note{background:#fff;border:1px solid var(--line);border-left:3px solid var(--warn);
padding:12px 14px;border-radius:6px;font-size:14px;margin:14px 0}
.fam{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 16px;
margin-bottom:10px}
.fam h3{margin:0 0 4px;font-size:15px}
.fam .meta{font-size:13px;color:var(--mut)}
.doc{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:24px 28px}
.doc h1{font-size:24px;margin:0 0 14px}
.doc h2{font-size:13px;margin-top:26px}
.doc table{font-size:13.5px}
.page{margin:22px 0 30px}
.page .pn{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut);
margin-bottom:8px}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.cols figure{margin:0}
.cols figcaption{font-size:12px;color:var(--mut);margin-bottom:6px}
.cols img{width:100%;border:1px solid var(--line);border-radius:4px;background:#fff}
@media (max-width:760px){.cols{grid-template-columns:1fr}}
a{color:#0b5cad;text-decoration:none}
a:hover{text-decoration:underline}
td a,.fam a,.doc a{text-decoration:underline}
td a:hover,.fam a:hover,.doc a:hover{text-decoration:none}
footer{color:var(--mut);font-size:12.5px;border-top:1px solid var(--line);margin-top:40px;
padding-top:14px}
"""


def _esc(value) -> str:
    return html.escape(str(value))


def _badge(tier: str) -> str:
    return f'<span class="badge {TIER_CLASS.get(tier, "warn")}">{_esc(tier)}</span>'


SEV_CLASS = {
    "identical": "ok",
    "subpixel": "ok",
    "minor": "warn",
    "visible": "warn",
    "major": "bad",
    "unknown": "fatal",
}


def _sev_badge(sev: str) -> str:
    return f'<span class="badge {SEV_CLASS.get(sev, "warn")}">{_esc(sev or "n/a")}</span>'


def _visual(doc: dict) -> tuple[str, float | None, str]:
    """Severity derived from the stored fraction, so band changes apply to old runs."""
    v = doc.get("visual") or {}
    if not v:
        return "", None, ""
    worst = v.get("worst")
    sev = pixels.severity(worst) if isinstance(worst, (int, float)) else v.get("severity", "")
    return sev, worst, v.get("pattern", "")


def _page(title: str, active: str, body: str, prefix: str = "") -> str:
    nav = [
        ("index.html", "Overview", "index"),
        ("runs.html", "Runs", "runs"),
        ("compare.html", "Compare", "compare"),
        ("baseline.html", "Baseline", "baseline"),
        ("families.html", "Families", "families"),
    ]
    links = "".join(
        f'<a href="{prefix}{href}" class="{"on" if key == active else ""}">{label}</a>'
        for href, label, key in nav
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(title)}</title><link rel="stylesheet" href="{prefix}assets/style.css"></head>
<body><header><div class="in"><h1>OOXML Fidelity Lab</h1><nav>{links}</nav></div></header>
<main>{body}</main></body></html>"""


def load_runs(runs_dir: Path) -> list[dict]:
    runs = []
    for results in sorted(runs_dir.glob("run-*/results.json")):
        try:
            data = json.loads(results.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        data["_dir"] = results.parent.name
        runs.append(data)
    runs.sort(key=lambda r: r.get("started", ""))
    return runs


def _family_docs(md: str) -> list[str]:
    match = re.search(r"\*\*Documents:\*\*\s*(.+)", md)
    if not match:
        return []
    return [part.strip() for part in match.group(1).split(",") if part.strip()]


def _family_status(md: str) -> str:
    match = re.search(r"\*\*Status:\*\*\s*([a-z-]+)", md)
    return match.group(1) if match else "unknown"


def _family_title(md: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+)$", md, re.MULTILINE)
    return match.group(1).strip() if match else fallback


def load_families(families_dir: Path) -> list[dict]:
    families = []
    if not families_dir.exists():
        return families
    for path in sorted(families_dir.glob("*.md")):
        if path.name == "TEMPLATE.md":
            continue
        text = path.read_text(encoding="utf-8")
        families.append(
            {
                "slug": path.stem,
                "path": path,
                "title": _family_title(text, path.stem),
                "status": _family_status(text),
                "docs": _family_docs(text),
                "text": text,
            }
        )
    return families


def _render_md(text: str) -> str:
    if _md is None:
        return f"<pre>{_esc(text)}</pre>"
    return _md.markdown(text, extensions=["tables", "fenced_code"])


def _find_pdfs(run_dir: Path, doc_id: str) -> tuple[Path | None, Path | None]:
    """Reference PDF from the oracle, candidate PDF from the renderer."""
    ref = run_dir / "ref" / doc_id / "document.pdf"
    cand_dir = run_dir / "cand" / doc_id
    cand = None
    if cand_dir.exists():
        found = sorted(cand_dir.glob("*.pdf"))
        cand = found[0] if found else None
    return (ref if ref.exists() else None, cand)


def _page_images(pdf: Path, media_dir: Path, prefix: str, zoom: float = 1.2, max_pages: int = 12):
    """Rasterise pages once and cache them on disk."""
    import pymupdf

    media_dir.mkdir(parents=True, exist_ok=True)
    images: list[str] = []
    doc = pymupdf.open(pdf)
    try:
        for index, page in enumerate(doc):
            if index >= max_pages:
                break
            name = f"{prefix}-{index + 1}.png"
            target = media_dir / name
            if not target.exists():
                pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
                pix.save(target)
            images.append(name)
    finally:
        doc.close()
    return images


def _build_document_pages(runs_dir: Path, run: dict, out_dir: Path, families: list[dict]) -> int:
    run_dir = runs_dir / run["_dir"]
    run_out = out_dir / "documents" / run["_dir"]
    media_root = out_dir / "media" / run["_dir"]
    built = 0

    for doc in run["documents"]:
        doc_id = doc["id"]
        ref_pdf, cand_pdf = _find_pdfs(run_dir, doc_id)
        if not ref_pdf and not cand_pdf:
            continue
        ref_imgs = _page_images(ref_pdf, media_root / doc_id, "word") if ref_pdf else []
        cand_imgs = _page_images(cand_pdf, media_root / doc_id, "cand") if cand_pdf else []

        rows = []
        for index in range(max(len(ref_imgs), len(cand_imgs))):
            base = f"../../media/{run['_dir']}/{doc_id}"
            left = (
                f'<img src="{base}/{ref_imgs[index]}" alt="Word page {index + 1}" loading="lazy">'
                if index < len(ref_imgs)
                else '<p class="mut">not rendered</p>'
            )
            right = (
                f'<img src="{base}/{cand_imgs[index]}" alt="Collabora page {index + 1}" loading="lazy">'
                if index < len(cand_imgs)
                else '<p class="mut">not rendered</p>'
            )
            rows.append(
                f'<div class="page"><div class="pn">page {index + 1}</div><div class="cols">'
                f"<figure><figcaption>Microsoft Word</figcaption>{left}</figure>"
                f"<figure><figcaption>Collabora</figcaption>{right}</figure>"
                "</div></div>"
            )

        t2 = doc.get("t2") or {}
        error = doc.get("error") or ""
        body = [
            f'<p><a href="../../index.html">&larr; overview</a> &middot; '
            f'<a href="../../runs/{_esc(run["_dir"])}.html">run {_esc(run["started"])}</a></p>',
            f'<h2 style="margin-top:0">{_esc(doc_id)}</h2>',
            f'<p>{_badge(doc["tier"])} &nbsp; score {doc["score"]:.2f}'
            f' &middot; median {t2.get("median_pt", "&mdash;")} pt'
            f' &middot; p95 {t2.get("p95_pt", "&mdash;")} pt</p>',
        ]
        if error:
            body.append(f'<div class="note">{_esc(error)}</div>')
        visual = doc.get("visual") or {}
        if visual:
            sev, worst, pat = _visual(doc)
            body.append(
                f'<p>Visual (parked, experimental): {_sev_badge(sev)}'
                f' &middot; worst page {float(worst or 0) * 100:.2f}% pixels changed'
                + (f' &middot; {_esc(pat)}' if pat and pat != "none" else "")
                + f' &middot; {visual.get("pages_ref", "?")} vs {visual.get("pages_cand", "?")} pages</p>'
            )
        t0 = doc.get("t0") or {}
        for entry in (t0.get("missing_detail") or [])[:3]:
            body.append(
                f'<div class="note">page {entry["page"]} lost {entry["count"]} token(s): '
                f'<span class="mono">{_esc(", ".join(entry["tokens"]))}</span></div>'
            )
        if (visual and visual.get("severity") not in (None, "identical")
                and ref_pdf and cand_pdf):
            heat = []
            for page in sorted(visual.get("pages", []),
                               key=lambda p: -p.get("fraction", 0))[:1]:
                if page.get("fraction", 0) <= 0:
                    continue
                img = media_root / doc_id / f"diff-{page['page']}.png"
                if not img.exists():
                    pixels.write_heatmap(ref_pdf, cand_pdf, int(page["page"]), img)
                if img.exists():
                    heat.append(
                        f'<figure><figcaption>page {page["page"]} &middot; '
                        f'{page["fraction"] * 100:.2f}% changed</figcaption>'
                        f'<img src="../../media/{_esc(run["_dir"])}/{_esc(doc_id)}/{img.name}"'
                        f' loading="lazy"></figure>'
                    )
            if heat:
                body.append('<h2>Pixel differences</h2><p class="mut">Red marks pixels that '
                            'differ from Word; grey is Word for reference. This is the only '
                            'view that can show a border, a fill or an image.</p>'
                            '<div class="cols">' + "".join(heat) + "</div>")
        related = [fam for fam in families if doc_id in fam["docs"]]
        if related:
            links = ", ".join(
                f'<a href="../../families/{_esc(fam["slug"])}.html">{_esc(fam["title"])}</a>'
                for fam in related
            )
            body.append(f'<div class="note">Known families: {links}</div>')
        if not rows:
            body.append('<p class="mut">No rendered pages available for this document.</p>')
        body.extend(rows)

        run_out.mkdir(parents=True, exist_ok=True)
        (run_out / f"{doc_id}.html").write_text(
            _page(doc_id, "index", "\n".join(body), prefix="../../")
        )
        built += 1
    return built


def _build_run_pages(runs_dir: Path, runs: list[dict], out_dir: Path) -> int:
    """One page per run, with its artifacts copied alongside."""
    import shutil as _shutil

    base = out_dir / "runs"
    base.mkdir(parents=True, exist_ok=True)
    built = 0

    for run in runs:
        run_id = run["_dir"]
        target = base / run_id
        target.mkdir(parents=True, exist_ok=True)
        for name in ("results.json", "report.md", "clusters.json"):
            source = runs_dir / run_id / name
            if source.exists():
                _shutil.copy2(source, target / name)

        summary = run.get("summary", {})
        body = [
            f'<p><a href="../index.html">&larr; overview</a></p>',
            f'<h2 style="margin-top:0">{_esc(run_id)}</h2>',
            f'<p class="mut">started <span class="mono">{_esc(run.get("started", "?"))}</span>'
            f' &middot; oracle <span class="mono">{_esc(run.get("oracle", "?"))}</span>'
            f' &middot; renderer <span class="mono">{_esc(str(run.get("renderer", "?")).split("@")[0])}</span></p>',
        ]
        if run.get("renderer", "").startswith("sha256"):
            body.append(f'<p class="mono mut">{_esc(run["renderer"])}</p>')

        body.append('<div class="cards">')
        for number, label in [
            (summary.get("count", 0), "documents"),
            (f'{summary.get("mean_score", 0):.3f}', "mean"),
            (f'{summary.get("weighted_mean", summary.get("mean_score", 0)):.3f}', "weighted"),
            (len(run.get("documents", [])), "rows"),
        ]:
            body.append(
                f'<div class="card"><div class="n">{_esc(number)}</div>'
                f'<div class="l">{_esc(label)}</div></div>'
            )
        body.append("</div>")

        body.append(
            '<p class="mut" style="margin-top:14px">artifacts: '
            f'<a href="results.json">results.json</a>'
            + (' &middot; <a href="report.md">report.md</a>'
               if (target / "report.md").exists() else "")
            + (' &middot; <a href="clusters.json">clusters.json</a>'
               if (target / "clusters.json").exists() else "")
            + "</p>"
        )

        body.append(
            "<h2>Documents</h2><table><tr><th>Document</th><th>Class</th><th>Tier</th>"
            "<th>Score</th><th>Median pt</th><th>Pages</th></tr>"
        )
        for doc in run.get("documents", []):
            t2 = doc.get("t2") or {}
            link = f"../../documents/{_esc(run_id)}/{_esc(doc['id'])}.html"
            body.append(
                f'<tr><td class="mono"><a href="{link}">{_esc(doc["id"])}</a></td>'
                f'<td class="mono mut">{_esc(doc.get("cls", "-"))}</td>'
                f"<td>{_badge(doc.get('tier', '?'))}</td>"
                f'<td class="num">{doc.get("score", 0):.2f}</td>'
                f'<td class="num">{t2.get("median_pt", "&mdash;")}</td>'
                f'<td><a href="{link}">view</a></td></tr>'
            )
        body.append("</table>")

        (base / f"{run_id}.html").write_text(_page(run_id, "runs", "\n".join(body), prefix="../"))
        built += 1
    return built


LANE_LABELS = {
    "upstream": "upstream image",
    "built-clean": "built-clean",
    "built-custom": "built-custom",
}


def _build_compare_page(runs: list[dict], lanes: dict, out_dir: Path,
                        runs_dir: Path, pages: int = 2) -> int:
    """Three lanes against one Word baseline, one row per document.

    Only documents that do not agree are listed: on a 325-document corpus the
    agreement is the boring part, and a page of identical rows hides the ones
    worth looking at. Each disagreement carries the rendered pages, Word
    included, so a tier change can be looked at rather than argued about.
    """
    by_id = {run["_dir"]: run for run in runs}
    names = [n for n in ("upstream", "built-clean", "built-custom") if lanes.get(n) in by_id]
    if len(names) < 2:
        return 0

    tiers = {name: {d["id"]: d for d in by_id[lanes[name]]["documents"]} for name in names}
    ids = sorted(set().union(*[set(t) for t in tiers.values()]))

    body = [
        '<p class="mut">The same corpus rendered three ways and scored against '
        'one set of Microsoft Word reference PDFs. Deltas here are renderer '
        'differences, not oracle variance.</p>',
        '<div class="cards">',
        f'<div class="card"><div class="n">{len(ids)}</div><div class="l">documents</div></div>',
    ]
    for name in names:
        run = by_id[lanes[name]]
        body.append(
            f'<div class="card"><div class="n">{run["summary"].get("mean_score", 0):.3f}</div>'
            f'<div class="l">{_esc(LANE_LABELS.get(name, name))}</div></div>'
        )
    body.append("</div>")

    body.append("<h2>Lanes</h2><table><tr><th>Lane</th><th>Run</th><th>Documents</th>"
                "<th>Passing</th><th>T0</th><th>Mean</th></tr>")
    for name in names:
        run = by_id[lanes[name]]
        s = run["summary"]
        t = s.get("by_tier", {})
        body.append(
            f'<tr><td>{_esc(LANE_LABELS.get(name, name))}</td>'
            f'<td><a class="mono" href="runs/{_esc(run["_dir"])}.html">{_esc(run["_dir"])}</a></td>'
            f'<td class="num">{s.get("count", 0)}</td>'
            f'<td class="num">{t.get("PASS", 0)}</td>'
            f'<td class="num">{t.get("T0", 0)}</td>'
            f'<td class="num">{s.get("mean_score", 0):.3f}</td></tr>'
        )
    body.append("</table>")

    differing = []
    identical = 0
    for doc_id in ids:
        vals = [tiers[n].get(doc_id, {}).get("tier") for n in names]
        if len({v for v in vals if v}) <= 1:
            identical += 1
            continue
        differing.append(doc_id)

    body.append(f"<h2>Where the lanes disagree ({len(differing)})</h2>")
    body.append(f'<p class="mut">{identical} of {len(ids)} documents score identically across '
                f'all {len(names)} lanes. Open a document to see the pages.</p>')

    # Word output is shared: every lane is scored against the same reference,
    # so it is shown once per document rather than once per lane.
    for doc_id in differing:
        cells = []
        for name in names:
            doc = tiers[name].get(doc_id)
            if not doc:
                cells.append('<td class="mut">&mdash;</td>')
                continue
            link = f"documents/{_esc(lanes[name])}/{_esc(doc_id)}.html"
            vis = (doc.get("visual") or {}).get("severity")
            sev, worst, pat = _visual(doc)
            cells.append(f'<td><a href="{link}">{_badge(doc["tier"])}</a>'
                         + (f' {_sev_badge(sev)}' if sev else "") + "</td>")
        head = "".join(f"<th>{_esc(LANE_LABELS.get(n, n))}</th>" for n in names)
        strip = []
        ref_pdf, _ = _find_pdfs(runs_dir / lanes[names[0]], doc_id)
        if ref_pdf:
            imgs = _page_images(ref_pdf, out_dir / "media" / lanes[names[0]] / doc_id,
                                "word", max_pages=pages)
            base = f"media/{lanes[names[0]]}/{doc_id}"
            figs = "".join(f'<figure><img src="{base}/{i}" alt="Word page" loading="lazy"></figure>'
                           for i in imgs)
            strip.append(f'<figure><figcaption>Microsoft Word</figcaption>{figs}</figure>')
        for name in names:
            _, cand_pdf = _find_pdfs(runs_dir / lanes[name], doc_id)
            if not cand_pdf:
                strip.append(f'<figure><figcaption>{_esc(LANE_LABELS.get(name, name))}</figcaption>'
                             f'<p class="mut">not rendered</p></figure>')
                continue
            imgs = _page_images(cand_pdf, out_dir / "media" / lanes[name] / doc_id,
                                "cand", max_pages=pages)
            base = f"media/{lanes[name]}/{doc_id}"
            figs = "".join(f'<figure><img src="{base}/{i}" alt="{_esc(name)} page" loading="lazy"></figure>'
                           for i in imgs)
            strip.append(f'<figure><figcaption>{_esc(LANE_LABELS.get(name, name))}</figcaption>{figs}</figure>')
        body.append(
            f'<details class="fam"><summary><span class="mono">{_esc(doc_id)}</span> &nbsp;'
            f'{"".join(cells[0:1])}</summary>'
            f'<table><tr><th>Document</th>{head}</tr><tr><td class="mono">{_esc(doc_id)}</td>'
            f'{"".join(cells)}</tr></table>'
            f'<div class="cols">{"".join(strip)}</div></details>'
        )

    (out_dir / "compare.html").write_text(_page("Compare", "compare", "\n".join(body)))
    return len(differing)


def build(runs_dir: Path, families_dir: Path, out_dir: Path, lanes: dict | None = None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "assets").mkdir(exist_ok=True)
    (out_dir / "assets" / "style.css").write_text(CSS.strip() + "\n")
    (out_dir / "families").mkdir(exist_ok=True)

    runs = load_runs(runs_dir)
    families = load_families(families_dir)
    latest = runs[-1] if runs else None
    compare_diffs = _build_compare_page(runs, lanes or {}, out_dir, runs_dir)

    # ---- overview ---------------------------------------------------------
    body = []
    if latest:
        s = latest["summary"]
        tiers = s.get("by_tier", {})
        real = latest["oracle"].startswith("windows")
        body.append(
            f'<p class="mut">Latest run '
            f'<a href="runs/{_esc(latest["_dir"])}.html" class="mono">{_esc(latest["_dir"])}</a>'
            f' &middot; oracle <span class="mono">{_esc(latest["oracle"])}</span>'
            f' &middot; renderer <span class="mono">{_esc(latest["renderer"].split("@")[0])}</span></p>'
        )
        if not real:
            body.append(
                '<div class="note">The oracle is a stub (the same engine as the renderer). '
                'Deltas from this run measure determinism, not fidelity against Microsoft Word.</div>'
            )
        cards = [
            (s.get("count", 0), "documents"),
            (s.get("mean_score", 0), "mean score"),
            (tiers.get("PASS", 0), "passing"),
            (sum(v for k, v in tiers.items() if k != "PASS"), "not passing"),
            (len(families), "families"),
        ]
        body.append('<div class="cards">')
        for number, label in cards:
            body.append(f'<div class="card"><div class="n">{_esc(number)}</div>'
                        f'<div class="l">{_esc(label)}</div></div>')
        body.append("</div>")

        body.append("<h2>Documents in this run</h2><table><tr><th>Document</th><th>Tier</th>"
                    "<th>Visual (parked)</th><th>Score</th><th>Median&nbsp;pt</th><th>p95&nbsp;pt</th>"
                    "<th>Fonts</th><th>Pages</th></tr>")
        for doc in latest["documents"]:
            t2 = doc.get("t2") or {}
            fonts = t2.get("fonts_missing") or []
            detail = doc.get("error") or ""
            link = f"documents/{_esc(latest['_dir'])}/{_esc(doc['id'])}.html"
            vis = (doc.get("visual") or {}).get("severity", "")
            sev, worst, pat = _visual(doc)
            vis_cell = (_sev_badge(sev) + (f' <span class="mut num">{worst * 100:.2f}%</span>'
                                           if isinstance(worst, (int, float)) else "")
                        if sev else '<span class="mut">&mdash;</span>')
            body.append(
                "<tr>"
                f'<td class="mono"><a href="{link}">{_esc(doc["id"])}</a></td>'
                f"<td>{_badge(doc['tier'])}</td>"
                f"<td>{vis_cell}</td>"
                f'<td class="num">{doc["score"]:.2f}</td>'
                f'<td class="num">{t2.get("median_pt", "&mdash;")}</td>'
                f'<td class="num">{t2.get("p95_pt", "&mdash;")}</td>'
                f'<td class="mono mut">{_esc(", ".join(fonts))}{_esc(detail)}</td>'
                f'<td><a href="{link}">view</a></td>'
                "</tr>"
            )
        body.append("</table>")
    else:
        body.append("<p>No runs yet. Run <code>make run-oracle</code>.</p>")

    (out_dir / "index.html").write_text(_page("Overview", "index", "\n".join(body)))

    doc_pages = 0
    for run in runs:
        doc_pages += _build_document_pages(runs_dir, run, out_dir, families)
    run_pages = _build_run_pages(runs_dir, runs, out_dir)

    # ---- runs -------------------------------------------------------------
    body = ["<h2>All runs</h2><table><tr><th>Run</th><th>Started</th><th>Oracle</th>"
            "<th>Docs</th><th>Mean</th><th>Tiers</th><th>Change</th></tr>"]
    previous = None
    for run in runs:
        mean = run["summary"].get("mean_score", 0)
        change = "&mdash;"
        if previous is not None:
            delta = mean - previous
            arrow = "&uarr;" if delta > 0 else ("&darr;" if delta < 0 else "=")
            change = f"{arrow} {abs(delta):.2f}"
        previous = mean
        tiers = ", ".join(f"{k}:{v}" for k, v in sorted(run["summary"].get("by_tier", {}).items()))
        body.append(
            f'<tr><td class="mono"><a href="runs/{_esc(run["_dir"])}.html">'
            f'{_esc(run["_dir"])}</a></td>'
            f'<td class="mono mut">{_esc(run.get("started", ""))}</td>'
            f'<td class="mono">{_esc(run["oracle"])}</td>'
            f'<td class="num">{run["summary"].get("count", 0)}</td>'
            f'<td class="num">{mean:.2f}</td>'
            f'<td class="mono mut">{_esc(tiers)}</td>'
            f'<td class="num">{change}</td></tr>'
        )
    if not runs:
        body.append("<tr><td colspan=6 class=mut>No runs yet.</td></tr>")
    body.append("</table>")
    (out_dir / "runs.html").write_text(_page("Runs", "runs", "\n".join(body)))

    # ---- baseline ---------------------------------------------------------
    body = ["<h2>Baseline</h2>"]
    if latest:
        summary = latest["summary"]
        body.append(
            f'<p class="mut">Run <span class="mono">{_esc(latest["started"])}</span>'
            f' &middot; oracle <span class="mono">{_esc(latest["oracle"])}</span></p>'
        )
        classes = summary.get("classes") or []
        if classes:
            body.append(
                "<table><tr><th>Document class</th><th>Documents</th><th>Mean</th>"
                "<th>Weight</th><th>Fatal</th><th>Tiers</th></tr>"
            )
            for row in classes:
                tiers = ", ".join(f"{k}:{v}" for k, v in (row.get("tiers") or {}).items())
                body.append(
                    f"<tr><td>{_esc(row['class'])}</td>"
                    f'<td class="num">{row["count"]}</td>'
                    f'<td class="num">{row["mean"]:.2f}</td>'
                    f'<td class="num">{row["weight"]}</td>'
                    f'<td class="num">{row["fatal"]}</td>'
                    f'<td class="mono mut">{_esc(tiers)}</td></tr>'
                )
            body.append("</table>")
            body.append(
                f'<div class="cards" style="margin-top:14px">'
                f'<div class="card"><div class="n">{summary.get("weighted_mean", 0):.3f}</div>'
                f'<div class="l">weighted mean</div></div>'
                f'<div class="card"><div class="n">{summary.get("count", 0)}</div>'
                f'<div class="l">documents</div></div>'
                f'<div class="card"><div class="n">{len(families)}</div>'
                f'<div class="l">known families</div></div></div>'
            )
        else:
            body.append('<p class="mut">This run predates per-class scoring.</p>')
    else:
        body.append("<p>No runs yet.</p>")

    if families:
        body.append("<h2>Known families</h2><table><tr><th>Family</th><th>Status</th></tr>")
        for fam in families:
            body.append(
                f'<tr><td><a href="families/{_esc(fam["slug"])}.html">{_esc(fam["title"])}</a></td>'
                f'<td class="mono">{_esc(fam["status"])}</td></tr>'
            )
        body.append("</table>")

    (out_dir / "baseline.html").write_text(_page("Baseline", "baseline", "\n".join(body)))

    # ---- families ---------------------------------------------------------
    body = ["<h2>Failure families</h2>"]
    # Families link to the newest run that measured each of their documents.
    newest: dict[str, str] = {}
    for run in runs:
        for doc in run.get("documents", []):
            newest[doc["id"]] = run["_dir"]
    if families:
        for fam in families:
            doc_links = []
            for doc_id in fam["docs"]:
                run_id = newest.get(doc_id)
                if run_id:
                    doc_links.append(
                        f'<a class="mono" href="documents/{run_id}/{_esc(doc_id)}.html">'
                        f"{_esc(doc_id)}</a>"
                    )
                else:
                    doc_links.append(f'<span class="mono mut">{_esc(doc_id)}</span>')
            meta = f'status <strong>{_esc(fam["status"])}</strong>'
            if doc_links:
                meta += " &middot; documents: " + ", ".join(doc_links)
            body.append(
                f'<div class="fam"><h3><a href="families/{_esc(fam["slug"])}.html">'
                f'{_esc(fam["title"])}</a></h3>'
                f'<div class="meta">{meta}</div></div>'
            )
            page = _page(fam["title"], "families",
                         f'<div class="doc">{_render_md(fam["text"])}</div>')
            (out_dir / "families" / f"{fam['slug']}.html").write_text(page)
    else:
        body.append("<p class=mut>No family records yet.</p>")
    (out_dir / "families.html").write_text(_page("Families", "families", "\n".join(body)))

    # ---- stamp ------------------------------------------------------------
    (out_dir / "build.json").write_text(json.dumps({
        "builtAt": datetime.now().isoformat(timespec="seconds"),
        "runs": len(runs),
        "families": len(families),
        "documents": doc_pages,
        "compare_diffs": compare_diffs,
    }, indent=2))

    return {"runs": len(runs), "families": len(families), "documents": doc_pages, "out": str(out_dir)}


def build_from_repo(repo: Path, out: Path | None = None) -> dict:
    out = out or repo / "private" / "site"
    # Do not wipe the output: rendered page images are cached there and
    # re-rasterising the whole run on every rebuild is slow.
    out.mkdir(parents=True, exist_ok=True)
    # three-lane.sh records which run each lane produced; without it the compare
    # page is simply not built rather than guessed at.
    lanes = {}
    lanes_file = repo / "private" / "build" / "three-lane.json"
    if lanes_file.exists():
        try:
            lanes = json.loads(lanes_file.read_text())
            # Older three-lane.sh wrote underscores; accept both spellings.
            lanes = {k.replace("_", "-"): v for k, v in lanes.items()}
        except (OSError, json.JSONDecodeError):
            lanes = {}
    return build(repo / "private" / "runs", repo / "docs" / "families", out, lanes=lanes)
