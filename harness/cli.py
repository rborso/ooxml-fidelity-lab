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
    return corpus_mod.validate(Path(args.manifest))


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
        res = cmp.compare(ref, cand, tol)
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
    c.set_defaults(func=cmd_check)

    g = sub.add_parser("gate", help="oracle determinism gate (render twice, compare)")
    g.add_argument("--workdir", default="private/runs/gate")
    g.add_argument("--limit", type=int, default=0)
    g.set_defaults(func=cmd_gate)

    r = sub.add_parser("run", help="render the corpus and score it")
    r.add_argument("--corpus", default=None, help="manifest; omit to use synthetic docs")
    r.add_argument("--out", default="private/runs")
    r.add_argument("--limit", type=int, default=0)
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
