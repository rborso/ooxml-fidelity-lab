"""Command-line entry point.

Everything here is operator-invoked. There is no CI: a run is a deliberate
script call with pinned inputs, and it leaves a recorded provenance trail.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from . import compare as cmp
from . import corpus as corpus_mod
from . import constructs, extract, minimize, pixels, placement, render, synth
from . import probe as probe_mod

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
    try:
        reaped = render.reap_stale()
        if reaped:
            print(f"removed {reaped} stale render container(s) from an earlier timeout",
                  file=sys.stderr)
    except render.RenderError:
        pass
    work = Path(args.out).resolve() / f"run-{started}"
    work.mkdir(parents=True, exist_ok=True)
    tol = _load_tolerances(Path(args.tolerances) if args.tolerances else None)

    classes: dict[str, str] = {}
    if args.corpus:
        version, items = corpus_mod.load(Path(args.corpus))
        items = corpus_mod.filter_split(items, args.split)
        docs = [i.path for i in items if i.exists]
        ids = [i.id for i in items if i.exists]
        classes = {i.id: i.cls for i in items}
        corpus_label = f"{args.corpus} v{version} split={args.split}"
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

    if args.renderer == "built-clean":
        if not render.CLEAN_SOFFICE:
            print("CLEAN_SOFFICE is not set: point it at the unpatched build", file=sys.stderr)
            return 2
        render_fn = render.render_built_clean
        image_used = render.CLEAN_SOFFICE
    elif args.renderer == "built-patched":
        if not render.CUSTOM_SOFFICE:
            print("CUSTOM_SOFFICE is not set: point it at the patched build", file=sys.stderr)
            return 2
        render_fn = render.render_built_patched
        image_used = render.CUSTOM_SOFFICE
    else:
        render_fn = render.render_collabora
        image_used = render.COLLABORA_IMAGE

    print(f"corpus:   {corpus_label}")
    print(f"oracle:   {args.oracle}")
    print(f"renderer: {args.renderer} {image_used.split('@')[0]}")
    print(f"output:   {work}\n")

    refs: dict[str, Path] = {}
    if args.reuse_ref:
        # Reuse Word's output from an earlier run. For a two-renderer comparison
        # this is not only faster: it guarantees both passes are measured against
        # the exact same reference rather than two separate oracle runs.
        src = Path(args.reuse_ref) / "ref"
        missing = []
        for doc_id in ids:
            pdf = src / doc_id / "document.pdf"
            if not pdf.exists():
                missing.append(doc_id)
                continue
            dst = work / "ref" / doc_id
            dst.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pdf, dst / "document.pdf")
            refs[doc_id] = dst / "document.pdf"
        print(f"oracle:   reused {len(refs)} reference PDF(s) from {src}"
              + (f", {len(missing)} missing" if missing else ""))
        oracle_results = {}
    elif args.oracle == "windows":
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
                            "cls": classes.get(doc_id, "unclassified"),
                            "t0": None, "t1": None, "t2": None, "error": reason})
            print(f"{'ORACLE':9s} 0.00  {doc_id}  ({reason})")
            continue

        try:
            cand_pdf = render_fn(docx, work / "cand" / doc_id)
        except render.RenderError as exc:
            # One document that will not render must not destroy a two-hour run,
            # and a silent skip would be worse: it would look like a pass.
            results.append({"id": doc_id, "tier": "RENDER-FAIL", "score": 0.0,
                            "cls": classes.get(doc_id, "unclassified"),
                            "t0": None, "t1": None, "t2": None, "error": str(exc)})
            print(f"{'RENDER':11s} 0.00  {doc_id}  ({exc})")
            continue
        ref = extract.extract_layout(refs[doc_id])
        cand = extract.extract_layout(cand_pdf)
        res = cmp.compare(ref, cand, {**tol, **overrides.get(doc_id, {})})
        # Geometry a human would notice: content in the margin, a block moved,
        # a box leaving the page. The tiered comparator reports medians, which
        # cannot see a single misplaced table.
        res["placement"] = placement.check(ref, cand)
        # Parked, off by default. Two engines never rasterise identically, so a
        # per-page pixel fraction measures hinting as much as layout. See
        # docs/PIXELS-PARKED.md for the measurements and for what has to change
        # before this is worth trusting.
        if args.pixels:
            res["visual"] = pixels.compare(refs[doc_id], cand_pdf)
        results.append({"id": doc_id, "tier": res["tier"], "score": res["score"],
                        "cls": classes.get(doc_id, "unclassified"), **res})
        visual = (res.get("visual") or {}).get("severity", "")
        print(f"{res['tier']:9s} {res['score']:.2f}  {doc_id}"
              + (f"  visual={visual}" if visual and visual != "identical" else ""))

    from .scoring import aggregate, weights_from_config

    agg = aggregate(results, weights_from_config(tol))
    summary = {
        "count": len(results),
        "by_tier": dict(Counter(r["tier"] for r in results)),
        "mean_score": round(sum(r["score"] for r in results) / len(results), 4) if results else 0.0,
        "weighted_mean": agg["weighted_mean"],
        "classes": agg["classes"],
    }

    payload = {
        "started": started,
        "corpus": corpus_label,
        "oracle": (
            "stub (collabora engine - not a fidelity reference)"
            if args.oracle == "stub"
            else f"windows:{args.domain}"
        ),
        "renderer": image_used,
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


def cmd_validate(args: argparse.Namespace) -> int:
    """Acceptance gate for a patch: compare a clean run with a custom run.

    A patch is acceptable only if it improves its target and degrades nothing
    else. Degradations are printed first and fail the command.
    """
    from .drift import load

    clean = {d["id"]: d for d in load(Path(args.clean_run).resolve()).get("documents", [])}
    custom = {d["id"]: d for d in load(Path(args.custom_run).resolve()).get("documents", [])}

    shared = sorted(set(clean) & set(custom))
    improvements, degradations, unchanged = [], [], 0
    for doc_id in shared:
        before, after = clean[doc_id], custom[doc_id]
        delta = round(float(after.get("score", 0)) - float(before.get("score", 0)), 4)
        row = (doc_id, before.get("tier"), after.get("tier"), delta)
        if delta < 0:
            degradations.append(row)
        elif delta > 0:
            improvements.append(row)
        else:
            unchanged += 1

    only_clean = sorted(set(clean) - set(custom))
    only_custom = sorted(set(custom) - set(clean))

    if degradations:
        print("DEGRADATIONS")
        for doc_id, before, after, delta in degradations:
            print(f"  {doc_id:26s} {before:9s} -> {after:9s} {delta:+.4f}")
    if improvements:
        print("IMPROVEMENTS")
        for doc_id, before, after, delta in improvements:
            print(f"  {doc_id:26s} {before:9s} -> {after:9s} {delta:+.4f}")
    if only_clean:
        print(f"MISSING FROM CUSTOM: {', '.join(only_clean[:10])}")
    if only_custom:
        print(f"ONLY IN CUSTOM: {', '.join(only_custom[:10])}")

    print(
        f"compared={len(shared)} improved={len(improvements)} "
        f"degraded={len(degradations)} unchanged={unchanged}"
    )
    return 1 if degradations else 0


def cmd_drift(args: argparse.Namespace) -> int:
    from .drift import load, reference_drift, score_drift

    a_dir = Path(args.run_a).resolve()
    b_dir = Path(args.run_b).resolve()
    a, b = load(a_dir), load(b_dir)

    drift = score_drift(a, b)
    for row in drift["classes"]:
        print(
            f"{row['class']:20s} before={row['before']} after={row['after']} "
            f"delta={row['delta']:+.4f}"
        )
    for change in drift["changes"][:25]:
        print(
            f"  {change['id']:26s} {change['before']:9s} -> {change['after']:9s} "
            f"{change['delta']:+.4f}"
        )
    ref = reference_drift(a_dir, b_dir, a, b)
    print(f"reference drift: documents={ref['documents']} mean={ref['mean']}")
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    from .split import extract

    info = extract(
        Path(args.doc).resolve(),
        Path(args.out).resolve(),
        args.contains,
        mode=args.mode,
    )
    print(json.dumps(info, indent=2))
    return 0


def cmd_harvest(args: argparse.Namespace) -> int:
    import yaml

    from .harvest import harvest

    corpus_dir = Path(args.corpus_dir).resolve()
    out_dir = Path(args.out).resolve()
    entries = harvest(
        args.page,
        out_dir,
        prefix=args.prefix,
        limit=args.limit,
        delay=args.delay,
    )
    for entry in entries:
        entry["path"] = str(Path(entry["path"]).resolve().relative_to(corpus_dir))

    sidecar = corpus_dir / f"{args.prefix}.yaml"
    previous: list[dict] = []
    if sidecar.exists():
        previous = (yaml.safe_load(sidecar.read_text()) or {}).get("items") or []
    merged = {item["id"]: item for item in previous}
    for entry in entries:
        merged[entry["id"]] = entry
    sidecar.write_text(
        yaml.safe_dump(
            {"items": [merged[key] for key in sorted(merged)]},
            sort_keys=False,
            allow_unicode=True,
        )
    )
    print(f"{len(merged)} item(s) in {sidecar}")
    return 0


def cmd_freeze(args: argparse.Namespace) -> int:
    from .corpus import holdout_digest

    _, items = corpus_mod.load(Path(args.manifest))
    digest = holdout_digest(items)
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(digest + "\n")
    count = sum(1 for item in items if item.split == "holdout")
    print(f"holdout documents={count} digest={digest} -> {target}")
    return 0


def cmd_archive(args: argparse.Namespace) -> int:
    from .archive import check_run

    rows, ok = check_run(Path(args.run).resolve())
    for row in rows:
        if not row["pass"]:
            print(f"  {Path(row['pdf']).name}: {'; '.join(row['issues'])}")
    failing = sum(1 for row in rows if not row["pass"])
    print(f"pdfs={len(rows)} failing={failing}")
    return 0 if ok else 1


def cmd_roundtrip(args: argparse.Namespace) -> int:
    from .roundtrip import convergence, format_churn

    doc = Path(args.doc).resolve()
    work = Path(args.work).resolve()
    conv = convergence(doc, work / "converge", hops=args.hops)
    churn = format_churn(doc, work / "churn")
    print(
        f"converged={conv['converged']} at_hop={conv['converged_at']} "
        f"hops={conv['hops']}"
    )
    print(
        f"docx->odt->docx changed={churn['changed']} "
        f"text {churn['text_before']}->{churn['text_after']}"
    )
    return 0 if conv["converged"] else 1


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
        pages=args.pages,
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
    r.add_argument("--split", default="all", choices=["all", "dev", "holdout"])
    r.add_argument("--tolerances", default="config/tolerances.yaml")
    r.add_argument("--oracle", default="stub", choices=["stub", "windows"])
    r.add_argument("--reuse-ref", default=None,
                   help="reuse reference PDFs from an earlier run instead of booting the oracle")
    r.add_argument("--renderer", default="image",
                   choices=["image", "built-clean", "built-patched"])
    r.add_argument("--pixels", action="store_true", help="enable the parked pixel-to-pixel tier (experimental, see docs/PIXELS-PARKED.md)")
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

    dr = sub.add_parser("drift", help="compare two runs: score drift and reference drift")
    dr.add_argument("--run-a", required=True)
    dr.add_argument("--run-b", required=True)
    dr.set_defaults(func=cmd_drift)

    va = sub.add_parser("validate", help="acceptance gate: clean run vs custom run")
    va.add_argument("--clean-run", required=True)
    va.add_argument("--custom-run", required=True)
    va.set_defaults(func=cmd_validate)

    ar = sub.add_parser("archive", help="archival checks on a run's PDFs")
    ar.add_argument("--run", required=True)
    ar.set_defaults(func=cmd_archive)

    fz = sub.add_parser("freeze", help="record the holdout split digest")
    fz.add_argument("--manifest", default="private/corpus/manifest.yaml")
    fz.add_argument("--out", default="private/corpus/holdout.sha256")
    fz.set_defaults(func=cmd_freeze)

    ex = sub.add_parser("extract", help="keep only body children containing given strings")
    ex.add_argument("--doc", required=True)
    ex.add_argument("--out", required=True)
    ex.add_argument("--contains", action="append", required=True)
    ex.add_argument("--mode", choices=["all", "any"], default="all")
    ex.set_defaults(func=cmd_extract)

    pr = sub.add_parser("probe", help="which pipeline stage lost the content")
    pr.add_argument("docx")
    pr.add_argument("--token", required=True)
    pr.add_argument("--soffice", default="")
    pr.add_argument("--timeout", type=int, default=180)
    pr.set_defaults(func=cmd_probe)

    cn = sub.add_parser("constructs", help="build or query the construct index")
    cn.add_argument("--corpus", default="private/corpus")
    cn.add_argument("--out", default="private/build/constructs.json")
    cn.add_argument("--rebuild", action="store_true")
    cn.add_argument("--query", default="")
    cn.set_defaults(func=cmd_constructs)

    mz = sub.add_parser("minimize", help="shrink a document until only the bug remains")
    mz.add_argument("docx")
    mz.add_argument("--token", required=True, help="text that should render but does not")
    mz.add_argument("--out", default="")
    mz.add_argument("--soffice", default="")
    mz.add_argument("--max-candidates", type=int, default=150)
    mz.set_defaults(func=cmd_minimize)

    return p


def cmd_minimize(args: argparse.Namespace) -> int:
    binary = args.soffice or os.environ.get("CLEAN_SOFFICE") or \
        "build/instdir-clean/program/soffice"
    if not Path(binary).exists():
        print(f"no binary at {binary}; pass --soffice", file=sys.stderr)
        return 2
    src = Path(args.docx)
    out = Path(args.out) if args.out else src.with_name(src.stem + ".min.docx")
    predicate = minimize.render_predicate(binary, args.token, Path("/tmp/minimize-render"))
    try:
        info = minimize.minimize_deep(src, out, predicate, args.max_candidates)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"elements {info['elements_before']} -> {info['elements_after']}"
          f" in {info['candidates_tried']} candidate(s)")
    print(f"wrote {info['out']}")
    return 0


def cmd_probe(args: argparse.Namespace) -> int:
    binary = args.soffice or os.environ.get("CLEAN_SOFFICE") or \
        "build/instdir-clean/program/soffice"
    if not Path(binary).exists():
        print(f"no binary at {binary}; pass --soffice", file=sys.stderr)
        return 2
    try:
        result = probe_mod.probe(Path(args.docx), args.token, binary, args.timeout)
    except probe_mod.ProbeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    for fmt, data in result["stages"].items():
        print(f"{fmt:5s} {'found' if data['found'] else 'missing':8s} "
              f"({data['occurrences']} occurrence(s))")
    print(f"\nverdict: {result['verdict']}")
    return 0 if result["stages"]["txt"]["found"] else 1


def cmd_constructs(args: argparse.Namespace) -> int:
    out = Path(args.out)
    index = {} if args.rebuild else constructs.load(out)
    if not index:
        corpus = Path(args.corpus)
        # The corpus is split across sidecars (bugzilla, hu-gov, denmark, derived,
        # known-good, ...). Reading only manifest.yaml indexed a third of it.
        sidecars = [p for p in sorted(corpus.glob("*.yaml")) if p.name != "overrides.yaml"]
        names: dict[str, str] = {}
        entries: list[tuple[str, Path]] = []
        if sidecars:
            import yaml
            for sidecar in sidecars:
                data = yaml.safe_load(sidecar.read_text()) or {}
                for item in data.get("items", []):
                    path = str(item.get("path", ""))
                    if not path.endswith((".docx", ".doc")):
                        continue
                    full = corpus / path
                    entries.append((item["id"], full))
                    names[str(full)] = item["id"]
        if entries:
            docs = [p for _, p in entries]
        else:
            docs = sorted(corpus.rglob("*.docx"))
        print(f"indexing {len(docs)} document(s)")
        index = constructs.build(docs, out, names)
    if args.query:
        hits = constructs.query(index, args.query)
        for name in hits:
            print(name)
        print(f"\n{len(hits)} of {len(index)} document(s) contain {args.query!r}")
        return 0
    print(f"{len(index)} document(s) indexed in {out}")
    counts: dict[str, int] = {}
    for data in index.values():
        for name, n in (data.get("counts") or {}).items():
            counts[name] = counts.get(name, 0) + n
    for name, n in sorted(counts.items(), key=lambda kv: -kv[1])[:10]:
        print(f"  {name:22s} {n}")
    return 0

    rt = sub.add_parser("roundtrip", help="convergence and format churn for one document")
    rt.add_argument("--doc", required=True)
    rt.add_argument("--work", default="private/roundtrip")
    rt.add_argument("--hops", type=int, default=5)
    rt.set_defaults(func=cmd_roundtrip)

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

    hv = sub.add_parser("harvest", help="collect documents linked from a public page")
    hv.add_argument("--page", required=True)
    hv.add_argument("--out", required=True)
    hv.add_argument("--corpus-dir", default="private/corpus")
    hv.add_argument("--prefix", required=True)
    hv.add_argument("--limit", type=int, default=25)
    hv.add_argument("--delay", type=float, default=0.5)
    hv.set_defaults(func=cmd_harvest)

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
