"""Command-line entry point.

Everything here is operator-invoked. There is no CI: a run is a deliberate
script call with pinned inputs, and it leaves a recorded provenance trail.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from . import compare as cmp
from . import corpus as corpus_mod
from . import extract, render, synth

DEFAULT_TOLERANCES = {"t2": {"median_pt_max": 1.0, "p95_pt_max": 4.0}}


def _load_tolerances(path: Path | None) -> dict:
    if not path or not path.exists():
        return DEFAULT_TOLERANCES
    import yaml

    data = yaml.safe_load(path.read_text()) or {}
    return data.get("tiers", DEFAULT_TOLERANCES) or DEFAULT_TOLERANCES


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def cmd_check(args: argparse.Namespace) -> int:
    return corpus_mod.validate(Path(args.manifest), strict=args.strict)


def cmd_gate(args: argparse.Namespace) -> int:
    """Determinism gate. Render each synthetic document twice and require an
    identical layout tree. Nothing downstream is meaningful until this passes."""
    work = Path(args.workdir).resolve()
    docs = work / "docs"
    paths = synth.write_all(docs)
    if args.limit:
        paths = paths[: args.limit]

    failures = 0
    print(f"renderer: {render.COLLABORA_IMAGE}")
    print(f"documents: {len(paths)}\n")

    for docx in paths:
        a = extract.extract_layout(render.render_collabora(docx, work / "a" / docx.stem))
        b = extract.extract_layout(render.render_collabora(docx, work / "b" / docx.stem))
        ha, hb = extract.layout_hash(a), extract.layout_hash(b)
        ok = ha == hb
        print(f"{'PASS' if ok else 'FAIL'}  {docx.stem:12s} {ha[:16]}")
        if not ok:
            failures += 1
            print(f"      second render: {hb[:16]}")

    print(f"\n{failures} failure(s)")
    return 0 if failures == 0 else 1


def cmd_run(args: argparse.Namespace) -> int:
    started = _stamp()
    work = Path(args.out).resolve() / f"run-{started}"
    work.mkdir(parents=True, exist_ok=True)
    tol = _load_tolerances(Path(args.tolerances) if args.tolerances else None)

    if args.corpus:
        version, items = corpus_mod.load(Path(args.corpus))
        docs = [i.path for i in items if i.exists]
        ids = [i.id for i in items if i.exists]
        corpus_label = f"{args.corpus} v{version}"
    else:
        paths = synth.write_all(work / "docs")
        docs = paths
        ids = [p.stem for p in paths]
        corpus_label = "synthetic"

    if args.limit:
        docs, ids = docs[: args.limit], ids[: args.limit]
    if args.only:
        wanted = {s.strip() for s in args.only.split(",") if s.strip()}
        pairs = [(d, i) for d, i in zip(docs, ids) if i in wanted]
        docs = [p[0] for p in pairs]
        ids = [p[1] for p in pairs]

    overrides = (
        corpus_mod.load_overrides(Path(args.corpus).parent / "overrides.yaml")
        if args.corpus
        else {}
    )

    print(f"corpus:   {corpus_label}")
    print(f"oracle:   {args.oracle}")
    print(f"renderer: {render.COLLABORA_IMAGE.split('@')[0]}")
    print(f"output:   {work}\n")

    refs: dict[str, Path] = {}
    if args.oracle == "windows":
        from .oracle import OracleError, WindowsOracle

        vo = WindowsOracle(domain=args.domain, timeout=args.boot_timeout)
        try:
            refs = vo.render_batch(dict(zip(ids, docs)), work / "ref")
        except OracleError as exc:
            print(f"oracle failed: {exc}", file=sys.stderr)
            return 2
        oracle_results = vo.results(work / "ref")
    else:
        oracle_results = {}
        for docx, doc_id in zip(docs, ids):
            refs[doc_id] = render.stub_oracle(docx, work / "ref" / doc_id)

    results = []
    for docx, doc_id in zip(docs, ids):
        if doc_id not in refs:
            reason = (oracle_results.get(doc_id) or {}).get("error") or "no reference PDF"
            results.append({"id": doc_id, "tier": "ORACLE-FAIL", "score": 0.0,
                            "t0": None, "t1": None, "t2": None, "error": reason})
            print(f"{'ORACLE':9s} 0.00  {doc_id}  ({reason})")
            continue

        cand_pdf = render.render_collabora(docx, work / "cand" / doc_id)
        ref = extract.extract_layout(refs[doc_id])
        cand = extract.extract_layout(cand_pdf)
        res = cmp.compare(ref, cand, {**tol, **overrides.get(doc_id, {})})
        results.append({"id": doc_id, "tier": res["tier"], "score": res["score"], **res})
        print(f"{res['tier']:9s} {res['score']:.2f}  {doc_id}")

    summary = {
        "count": len(results),
        "by_tier": dict(Counter(r["tier"] for r in results)),
        "mean_score": round(sum(r["score"] for r in results) / len(results), 4) if results else 0.0,
    }

    payload = {
        "started": started,
        "corpus": corpus_label,
        "oracle": (
            "stub (collabora engine - not a fidelity reference)"
            if args.oracle == "stub"
            else f"windows:{args.domain}"
        ),
        "renderer": render.COLLABORA_IMAGE,
        "tolerances": tol,
        "summary": summary,
        "documents": results,
    }
    (work / "results.json").write_text(json.dumps(payload, indent=2))
    (work / "report.md").write_text(_report(payload))

    print(f"\n{summary['by_tier']}  mean={summary['mean_score']}")
    print(f"report: {work / 'report.md'}")
    return 0


def _report(payload: dict) -> str:
    lines = [
        "# Run report",
        "",
        f"- started: `{payload['started']}`",
        f"- corpus: `{payload['corpus']}`",
        f"- oracle: {payload['oracle']}",
        f"- renderer: `{payload['renderer']}`",
        f"- documents: {payload['summary']['count']}",
        f"- mean score: {payload['summary']['mean_score']}",
        f"- tiers: {payload['summary']['by_tier']}",
        "",
    ]
    if payload["oracle"].startswith("stub"):
        lines += [
            "> The oracle is a stub. Deltas here measure determinism, not fidelity",
            "> against Microsoft Word.",
            "",
        ]
    lines += [
        "| Document | Tier | Score | median pt | p95 pt | fonts missing |",
        "|---|---|---|---|---|---|",
    ]
    for doc in payload["documents"]:
        t2 = doc.get("t2") or {}
        lines.append(
            "| {id} | {tier} | {score:.2f} | {med} | {p95} | {fonts} |".format(
                id=doc["id"],
                tier=doc["tier"],
                score=doc["score"],
                med=t2.get("median_pt", "-"),
                p95=t2.get("p95_pt", "-"),
                fonts=", ".join(t2.get("fonts_missing") or []) or "-",
            )
        )
    return "\n".join(lines) + "\n"


def cmd_crosscheck(args: argparse.Namespace) -> int:
    from .crosscheck import crosscheck

    rows, summary = crosscheck(Path(args.run).resolve(), threshold=args.threshold)
    if rows and rows[0].get("error"):
        print(rows[0]["error"], file=sys.stderr)
        return 2
    for row in rows:
        if row.get("status") not in (None, "ok"):
            print(f"  {row['status']:10s} {row['agreement']:.4f}  {row['pdf']}")
    print(
        "documents={documents} median={median:.4f} min={min:.4f} "
        "outliers={outliers} threshold={threshold}".format(**summary)
    )
    return 0 if summary["ok"] else 1


def cmd_cluster(args: argparse.Namespace) -> int:
    from .cluster import cluster

    run_dir = Path(args.run).resolve()
    data = json.loads((run_dir / "results.json").read_text())
    paths: dict[str, Path] = {}
    if args.corpus:
        _, items = corpus_mod.load(Path(args.corpus))
        paths = {item.id: item.path for item in items}

    docs = []
    for doc in data["documents"]:
        path = paths.get(doc["id"])
        if path and path.exists():
            docs.append((doc["id"], path, doc["tier"]))

    groups = cluster(docs)
    for group in groups:
        print(f"{group['size']:3d}  {group['key']}  {group['tier']:9s}  {group['description']}")
        print("      " + ", ".join(group["documents"][:8]))
    (run_dir / "clusters.json").write_text(json.dumps(groups, indent=2))
    print(f"clusters: {len(groups)} over {len(docs)} documents -> {run_dir / 'clusters.json'}")
    return 0


def cmd_minimize(args: argparse.Namespace) -> int:
    import shlex
    import subprocess

    from .minimize import minimize_docx

    command = shlex.split(args.predicate_command)

    def predicate(candidate: Path) -> bool:
        proc = subprocess.run([*command, str(candidate)], capture_output=True)
        return proc.returncode == 0

    info = minimize_docx(
        Path(args.doc).resolve(),
        Path(args.out).resolve(),
        predicate,
        max_candidates=args.max_candidates,
    )
    print(json.dumps(info, indent=2))
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    from .fetch import fetch, to_yaml

    entries = fetch(
        base=args.base,
        out_dir=Path(args.out),
        limit=args.limit,
        query=args.query,
        delay=args.delay,
    )
    fragment = Path(args.out) / "manifest-fragment.yaml"
    fragment.write_text(to_yaml(entries))
    print(f"manifest fragment: {fragment}")
    return 0 if entries else 1


def cmd_site(args: argparse.Namespace) -> int:
    from .site import build_from_repo

    root = Path(args.repo).resolve()
    info = build_from_repo(root, Path(args.out) if args.out else None)
    print(f"built site: {info['runs']} runs, {info['families']} families -> {info['out']}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    run_dir = Path(args.run).resolve()
    data = json.loads((run_dir / "results.json").read_text())
    out = _report(data)
    target = Path(args.out) if args.out else run_dir / "report.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(out)
    print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="harness", description="OOXML fidelity harness")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("check", help="validate the corpus manifest")
    c.add_argument("--manifest", required=True)
    c.add_argument("--strict", action="store_true", help="missing licence is an error")
    c.set_defaults(func=cmd_check)

    g = sub.add_parser("gate", help="oracle determinism gate (render twice, compare)")
    g.add_argument("--workdir", default="private/runs/gate")
    g.add_argument("--limit", type=int, default=0)
    g.set_defaults(func=cmd_gate)

    r = sub.add_parser("run", help="render the corpus and score it")
    r.add_argument("--corpus", default=None, help="manifest; omit to use synthetic docs")
    r.add_argument("--out", default="private/runs")
    r.add_argument("--limit", type=int, default=0)
    r.add_argument("--only", default="", help="comma-separated document ids")
    r.add_argument("--tolerances", default="config/tolerances.yaml")
    r.add_argument("--oracle", default="stub", choices=["stub", "windows"])
    r.add_argument("--domain", default="win11-0")
    r.add_argument("--boot-timeout", type=int, default=900)
    r.set_defaults(func=cmd_run)

    rep = sub.add_parser("report", help="re-render a report from results.json")
    rep.add_argument("--run", required=True)
    rep.add_argument("--out", default=None)
    rep.set_defaults(func=cmd_report)

    site = sub.add_parser("site", help="build the static report site")
    site.add_argument("--repo", default=".")
    site.add_argument("--out", default=None)
    site.set_defaults(func=cmd_site)

    cx = sub.add_parser("crosscheck", help="compare extractor tokens with pdftotext")
    cx.add_argument("--run", required=True)
    cx.add_argument("--threshold", type=float, default=0.99)
    cx.set_defaults(func=cmd_crosscheck)

    cl = sub.add_parser("cluster", help="group failing documents by construct signature")
    cl.add_argument("--run", required=True)
    cl.add_argument("--corpus", default="private/corpus/manifest.yaml")
    cl.set_defaults(func=cmd_cluster)

    mn = sub.add_parser("minimize", help="ddmin a document against a failure predicate")
    mn.add_argument("--doc", required=True)
    mn.add_argument("--out", required=True)
    mn.add_argument(
        "--predicate-command",
        required=True,
        help="shell command run with the candidate path appended; exit 0 = still failing",
    )
    mn.add_argument("--max-candidates", type=int, default=400)
    mn.set_defaults(func=cmd_minimize)

    f = sub.add_parser("fetch", help="download DOCX attachments from a bug tracker")
    f.add_argument("--out", default="private/corpus/bugzilla")
    f.add_argument("--limit", type=int, default=25)
    f.add_argument("--pages", type=int, default=1, help="search pages to walk")
    f.add_argument("--query", default="docx")
    f.add_argument("--base", default="https://bugs.documentfoundation.org")
    f.add_argument("--delay", type=float, default=0.4)
    f.set_defaults(func=cmd_fetch)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except render.RenderError as exc:
        print(f"render failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
