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

TIER_CLASS = {
    "PASS": "ok",
    "T2-fonts": "warn",
    "T2": "warn",
    "ORDER": "warn",
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
footer{color:var(--mut);font-size:12.5px;border-top:1px solid var(--line);margin-top:40px;
padding-top:14px}
"""


def _esc(value) -> str:
    return html.escape(str(value))


def _badge(tier: str) -> str:
    return f'<span class="badge {TIER_CLASS.get(tier, "warn")}">{_esc(tier)}</span>'


def _page(title: str, active: str, body: str) -> str:
    nav = [
        ("index.html", "Overview", "index"),
        ("runs.html", "Runs", "runs"),
        ("families.html", "Families", "families"),
    ]
    links = "".join(
        f'<a href="{href}" class="{"on" if key == active else ""}">{label}</a>'
        for href, label, key in nav
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(title)}</title><link rel="stylesheet" href="assets/style.css"></head>
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
                "text": text,
            }
        )
    return families


def _render_md(text: str) -> str:
    if _md is None:
        return f"<pre>{_esc(text)}</pre>"
    return _md.markdown(text, extensions=["tables", "fenced_code"])


def build(runs_dir: Path, families_dir: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "assets").mkdir(exist_ok=True)
    (out_dir / "assets" / "style.css").write_text(CSS.strip() + "\n")
    (out_dir / "families").mkdir(exist_ok=True)

    runs = load_runs(runs_dir)
    families = load_families(families_dir)
    latest = runs[-1] if runs else None

    # ---- overview ---------------------------------------------------------
    body = []
    if latest:
        s = latest["summary"]
        tiers = s.get("by_tier", {})
        real = latest["oracle"].startswith("windows")
        body.append(
            f'<p class="mut">Latest run <span class="mono">{_esc(latest["started"])}</span> '
            f'&middot; oracle <span class="mono">{_esc(latest["oracle"])}</span> '
            f'&middot; renderer <span class="mono">{_esc(latest["renderer"].split("@")[0])}</span></p>'
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
                    "<th>Score</th><th>Median&nbsp;pt</th><th>p95&nbsp;pt</th>"
                    "<th>Fonts</th></tr>")
        for doc in latest["documents"]:
            t2 = doc.get("t2") or {}
            fonts = t2.get("fonts_missing") or []
            detail = doc.get("error") or ""
            body.append(
                "<tr>"
                f'<td class="mono">{_esc(doc["id"])}</td>'
                f"<td>{_badge(doc['tier'])}</td>"
                f'<td class="num">{doc["score"]:.2f}</td>'
                f'<td class="num">{t2.get("median_pt", "&mdash;")}</td>'
                f'<td class="num">{t2.get("p95_pt", "&mdash;")}</td>'
                f'<td class="mono mut">{_esc(", ".join(fonts))}{_esc(detail)}</td>'
                "</tr>"
            )
        body.append("</table>")
    else:
        body.append("<p>No runs yet. Run <code>make run-oracle</code>.</p>")

    (out_dir / "index.html").write_text(_page("Overview", "index", "\n".join(body)))

    # ---- runs -------------------------------------------------------------
    body = ["<h2>All runs</h2><table><tr><th>Started</th><th>Oracle</th><th>Docs</th>"
            "<th>Mean</th><th>Tiers</th><th>Change</th></tr>"]
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
            f'<tr><td class="mono">{_esc(run["started"])}</td>'
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

    # ---- families ---------------------------------------------------------
    body = ["<h2>Failure families</h2>"]
    if families:
        for fam in families:
            body.append(
                f'<div class="fam"><h3><a href="families/{_esc(fam["slug"])}.html">'
                f'{_esc(fam["title"])}</a></h3>'
                f'<div class="meta">status <strong>{_esc(fam["status"])}</strong></div></div>'
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
    }, indent=2))

    return {"runs": len(runs), "families": len(families), "out": str(out_dir)}


def build_from_repo(repo: Path, out: Path | None = None) -> dict:
    out = out or repo / "private" / "site"
    if out.exists():
        shutil.rmtree(out)
    return build(repo / "private" / "runs", repo / "docs" / "families", out)
