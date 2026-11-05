# Bootstrap: what can start before the Windows VM exists

## The architectural fact that makes this possible

The oracle is a **swappable adapter** (DESIGN.md §3.2). Only that adapter needs Word.
Everything upstream and downstream of it — corpus, extraction, comparison, scoring,
minimization, clustering, reporting — consumes a PDF and does not care which program
produced it.

So build the pipeline against a **stub oracle**: same interface, same file-queue protocol,
same output shape, but backed by `soffice` in a container instead of Word. When the Windows
VM is ready, you swap one adapter and re-baseline. Nothing else changes.

## What is genuinely blocked on Windows

Only three things:

1. The real oracle adapter (`pywin32` COM driver).
2. The determinism gate measured against Word (SETUP.md §10).
3. Published reference PDFs and therefore real scores.

Everything else can proceed now.

---

## Work packages, in dependency order

### WP1 — Environment (can start immediately)

Available on this node as of now:

| Tool | Status |
|---|---|
| Python 3.12.13 | ✅ |
| `make` 4.4.1 | ✅ |
| `podman` 5.8.2 (rootless working) | ✅ |
| `git` 2.52.0 | ✅ |
| `docker` | ❌ not installed — use podman, same OCI images |
| system `pip3` | ❌ missing — `python3 -m venv` bootstraps pip inside the venv |
| `unzip` / `qpdf` | ❌ — not needed; Python `zipfile` and `pikepdf` cover it |

```bash
make venv     # creates .venv/ with pip, then installs deps
make test
```

### WP2 — Corpus tooling (no renderers needed)

- Pydantic models for the manifest schema (`corpus/manifest.example.yaml`).
- Ingestion: hash, dedupe, classify, assign `dev`/`holdout` split.
- Stratification report — verify the 70/20/10 target before it drifts.
- **Licence enforcement:** refuse to mark an item `publishable` without a resolvable
  licence. This is the guard that keeps the public repo clean, and it is much easier to
  build now than to add after 2,000 items exist.

### WP3 — Corpus acquisition

- Harvest DOCX attachments from LibreOffice and OnlyOffice bug trackers. These are already
  minimized by reporters and already labelled with a failure description — the cheapest
  high-quality corpus available.
- Record source URL, attachment licence terms, and the upstream bug ID per item.
- Do **not** ingest real government documents yet: that is gated on the redaction policy.

### WP4 — Synthetic generator

`python-docx` plus direct XML injection for constructs the library cannot express.

Start with the families DESIGN.md §3.9 anticipates: numbering definitions, conditional
table styles (`w:tblStylePr`), floating tables (`w:tblpPr`), text frames (`w:framePr`),
content controls (`w:sdt`), complex fields (`w:fldChar`), `w:compat` flags.

Output goes to `corpus/public/` so it is committable and non-confidential. This becomes the
permanent regression suite.

### WP5 — PDF → layout tree extractor

PyMuPDF, per DESIGN.md §3.4.

Validate it without Word: render the same document twice with `soffice`, extract both, and
assert identical trees. That proves extraction is deterministic. Then verify font-name
canonicalization (`ABCDEF+Calibri` vs `Calibri,Bold`) and coordinate rounding.

### WP6 — Comparators T0/T1

**You can validate the entire comparison engine without Microsoft.** Run LibreOffice and
OnlyOffice on the same corpus and diff them against each other. Two independent engines,
two real PDFs, no Word.

This is not a throwaway step. It proves the comparator's correctness, and the resulting
disagreement list is directly useful (see WP9).

### WP7 — Job queue + stub oracle

Implement the file protocol from SETUP.md §5 and a `soffice`-backed oracle adapter. This
exercises the real orchestration path: job write → poll → render → collect → record.

### WP8 — Run store + provenance

DuckDB schema from DESIGN.md §3.12, plus the version guard: abort the run if the VM image
hash or any container digest drifted from config. Build it now, because it is the thing
that makes numbers comparable later.

### WP9 — Report generator

The first real report is not "LibreOffice vs Word". It is:

> **Where do two open-source engines disagree on the same document?**

That is exactly the underspecified-construct detector from GOALS.md, and it requires no
Microsoft software. It is publishable on its own merits, and it is the same report
machinery you will use for the Word comparison later.

---

## Why the stub phase is not wasted work

The deliverable of WP1–WP9 is the *entire* harness minus one adapter. The report format,
the schema, the scoring model, the determinism checks, the minimizer — all of it is
exercised and validated. When Word arrives, you write ~200 lines of COM glue, re-baseline,
and start producing reference scores.

Building it the other way round — waiting for Windows — is the sequencing mistake that
kills projects like this.

---

## Resource note for this node

This machine (4 cores, 7 GB RAM, 30 GB free) is correctly scoped as the **workstation**:

- Enough for: code, `soffice` conversions in podman, corpus tooling, the run store for a
  small corpus.
- Not enough for: OnlyOffice Document Server (~4 GB RAM alone), or the artifact store
  (expect 100–200 GB once the corpus reaches a few thousand documents and round-trip
  variants are retained).

Keep renderers and artifacts on the larger host. Only the workstation role belongs here.

---

## Suggested order

1. WP1 + WP2
2. WP4 → generate synthetic fixtures (WP3 can run in parallel, it is pure I/O)
3. WP5 + WP6 → prove extraction and comparison with LibreOffice vs OnlyOffice
4. WP7 + WP8 → exercise the real orchestration and provenance path
5. WP9 → first published report, no Microsoft involved
6. Then: Windows VM → real oracle adapter → determinism gate → re-baseline
