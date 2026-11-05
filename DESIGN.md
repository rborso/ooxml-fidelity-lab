# OOXML Fidelity Lab — Design

Status: draft v0.1
Companion: [GOALS.md](./GOALS.md)

---

## 1. Design principles

1. **Pinned oracle.** All scores compare against one specific Word build on one specific
   VM. Floating references make every number meaningless.
2. **Tiered, content-first.** Never report geometry before answering "is the content
   intact?" Content loss is fatal; a 3pt shift is cosmetic.
3. **Differential, not absolute.** We measure divergence from a reference, not
   conformance to a spec that does not exist for layout.
4. **Full provenance.** Every score decomposes into (corpus item, inputs, software
   versions, harness version, run id). No unreproducible numbers.
5. **Convergence over repetition.** A round-trip is measured for whether it reaches a
   fixed point, not for how many times you can loop it.
6. **Vendor-neutral.** No suite maintainer owns or gates the score.
7. **Cluster, then fix.** The unit of work is a failure family, not a document.
8. **Operator-invoked runs.** There is no CI/CD. Every run is a deliberate script
   invocation with pinned inputs and a recorded provenance trail, so any published number
   can be reproduced from the command line by someone reading the run record.

---

## 2. Architecture

```
                    ┌──────────────────────┐
                    │  corpus store        │
                    │  (stratified, hashed)│
                    └──────────┬───────────┘
                               │
        ┌──────────────────────┼───────────────────────┐
        │                      │                       │
┌───────▼────────┐   ┌─────────▼─────────┐   ┌─────────▼─────────┐
│ Word oracle    │   │ suite renderer A  │   │ suite renderer B  │
│ (pinned VM/COM)│   │ (Collab/OnlyOffice)│  │ (optional)        │
└───────┬────────┘   └─────────┬─────────┘   └─────────┬─────────┘
        │                      │                       │
        ▼                      ▼                       ▼
   reference.pdf          candidate.pdf           candidate.pdf
        │                      │                       │
        └──────────┬───────────┴───────────────────────┘
                   ▼
          ┌────────────────────┐
          │ layout extractor   │  PDF → normalized layout tree
          └─────────┬──────────┘
                    ▼
          ┌────────────────────┐        ┌────────────────────┐
          │ comparator (T0–T3) │───────▶│ scorer + run store │
          └─────────┬──────────┘        └─────────┬──────────┘
                    │                             ▼
                    ▼                     ┌────────────────┐
          ┌────────────────────┐          │ reports /      │
          │ minimizer + clus-  │          │ release delta  │
          │ terer + synthesizer│          └────────────────┘
          └─────────┬──────────┘
                    ▼
          minimized reproducers → upstream issues
```

Orthogonal pipeline, run per corpus item:

```
round-trip:  DOCX ──▶ suite A ──▶ DOCX ──▶ suite B ──▶ DOCX …  (mutation matrix)
             measure convergence + semantic XML drift at each hop
```

---

## 3. Components

### 3.1 Corpus store
- Immutable, content-addressed by SHA-256 of the original file.
- Every item carries metadata: source, document class, provenance, licence/redaction
  status, expected-construct tags, and the Word build that authored it.
- Stratification targets: ~70% real documents from the target population, ~20% upstream
  bug-tracker attachments (already minimized and labelled by reporters), ~10% synthetic
  single-construct documents.
- Split: `dev` / `holdout`. Fixes may be tuned on `dev`; published scores use `holdout`.

### 3.2 Word oracle
- Windows VM, snapshotted, updates disabled, one licensed Word build, fixed locale.
- **Fixed default printer, never changed.** Word layout can depend on printer driver
  metrics.
- Export via **Export → PDF**, never a Print-to-PDF driver (different codepath).
- Automated with `pywin32`/COM, one document per fresh Word process (Word leaks and
  carries state).
- Determinism gate: render each item twice; identical layout trees or the item is
  quarantined, not scored.

### 3.3 Suite renderers
- Each renderer is an adapter behind a single interface:
  `render(docx_path) -> pdf_path` and `convert(docx_path) -> docx_path`.
- Containerized per version. Version string captured in every artifact.
- Initial targets: Collabora Online (headless), OnlyOffice Docs, LibreOffice desktop
  (`soffice --convert-to pdf`). `x2t` exposed as a separate conversion-only adapter for
  round-trip isolation.

### 3.4 Layout extractor
- PDF → normalized layout tree:
  - text spans: `text, bbox, font_name, font_size, color, page`
  - lines and their break points
  - drawn geometry: rects, lines, paths (normalized)
  - image placements: bbox, hash
- Implementation: PyMuPDF `page.get_text("dict")`, plus a geometry pass.
- Rasterization is a *rendering of last resort for human review*, not a score input.

### 3.5 Comparators
Tiered, evaluated in order, short-circuiting:

| Tier | Assertion | On failure |
|---|---|---|
| T0 | Same text content present per page (multiset) | fatal — data loss |
| T0-order | Same words, different reading order | `ORDER`, not fatal |
| T1 | Same page count, line count, line break positions | structural |
| T2 | Per-word bbox delta within tolerance (median and p95, in points) | cosmetic |
| T3 | Raster similarity (SSIM / perceptual hash) | informational only |

Content presence and content order are separate assertions. Losing a word is fatal;
visiting the same words in a different order is a reading-order difference — real, worth
reporting, but scoring it as data loss buries the findings that matter. Text boxes and
multi-column layouts produce order differences constantly.

Font substitution report is emitted alongside T2: which font names were requested,
which were found, which were substituted.

### 3.6 Scorer
- Per-document: `score = f(T0, T1, T2)` — T0 failure caps the score at 0.
- Per-class aggregate: distribution, not mean. Report p50 / p95 and the count of fatal
  failures. A mean hides the tail, and the tail is the point.
- Store every run; compute **release deltas** by diffing consecutive runs of the same
  corpus against different software versions.

### 3.7 Round-trip engine
Four mutation patterns — they break different things:

| Pattern | Path | Catches |
|---|---|---|
| Pass-through | open → save | pure conversion loss |
| Format churn | DOCX → ODT → DOCX | cross-format loss |
| Edited | open → mutate → save | style/numbering/revision loss |
| Mixed-author | Word edit → suite edit → Word edit | the real-world case |

Mutation is deterministic and seeded (insert paragraph, apply style, add/accept revision,
add table row, insert comment) so runs are reproducible.

**Convergence criterion:** iterate to a fixed point, typically 3–5 hops. If
`state(n+1) == state(n)`, the document has stabilized and is safe in a mixed-author
workflow. Continuous drift is a structural bug and is reported as such.

### 3.8 Minimizer
- Delta-debugging (`ddmin`) over `document.xml` / zip parts, preserving the failure
  signature.
- Failure signature = the tiered diff tuple, not a visual judgement.
- Output: smallest real document that still fails, plus a construct inventory.
- This is the component that converts "1,400 broken files" into "eleven bugs."

### 3.9 Families and lifecycle

The unit of work is a **family**, not a document: 400 broken files are usually ~11 bugs. A
family is keyed on (construct signature, diff signature) — e.g. "all lines inside table
cells shift +3pt" → row-height handling.

Every family moves through one state machine. Steps 2–3 are mandatory before any fix is
proposed: an explanation without a minimal reproducer is a hypothesis, not a root cause.

| # | Step | Produces |
|---|---|---|
| 1 | **detect** | family key, affected documents, tier |
| 2 | **isolate** | ddmin minimal reproducer + one-construct synthetic case |
| 3 | **explain** | root cause, marked `hypothesis` or `confirmed` |
| 4 | **classify** | fix class (table below) |
| 5 | **decide** | fix here / fix upstream / change templates / wontfix |
| 6 | **test-first** | the failing synthetic case committed as a regression test |
| 7 | **fix** | the changed artifact, recorded |
| 8 | **verify** | family closed **and** corpus-wide no-regression sweep, plus score delta |
| 9 | **record** | append-only observation; reopenable when a release regresses it |

**Fix classes.** Most families should die at the first two and never reach a patch:

| Class | Cost | Meaning |
|---|---|---|
| `config` | trivial | fonts, locale, settings |
| `template` | trivial | change the document, not the software |
| `integration` | medium | embedding / storage glue |
| `renderer` | expensive | patch upstream |
| `adjudicate` | zero | Word is wrong; do not replicate the bug |
| `invalid` | zero | harness artifact / false positive |

`adjudicate` and `invalid` are first-class outcomes. Without them the backlog fills with
items where matching Word would make the product worse, and with issues that are our own
bugs — which differential harnesses generate constantly.

**Ranking:** affected documents × usage weight of the document class. Usage weight is a
human input: a 2pt shift on a signature page matters; the same shift in a 40-page annex
does not.

### 3.10 Synthetic generator
- `build(construct_id) -> minimal.docx` exercising exactly one OOXML construct, with
  parameterized variants.
- Used to (a) confirm a family's root cause in isolation, (b) create the permanent
  regression test attached to any upstream fix.
- **Test-first:** written while it is still failing, committed, then fixed — so it becomes
  the regression test rather than an afterthought.
- Build on a template engine over `python-docx` plus direct XML injection for constructs
  the library cannot express.

### 3.11 Reporter
- Per-run report: class scores, fatal-failure count, family list, release delta.
- **One Markdown page per family under `docs/families/`** (template:
  `docs/families/TEMPLATE.md`) — reproduce command, mechanism, fix class, decision, retest
  delta. This is the most durable artifact the project produces: a ten-minute fix for
  anyone in any country.
- Machine-readable JSON alongside human-readable output so a script or the operator can
  gate on it.

### 3.12 Run store
- Append-only records of every run. Never mutate history; supersede.
- Schema sketch:

```
corpus_item(id, sha256, class, source, word_build_authored, tags[], licence, split)

run(id, started_at, harness_version, oracle_build, oracle_vm_image,
    renderer_name, renderer_version, software_commit)

render_artifact(id, run_id, corpus_item_id, kind[reference|candidate|roundtrip],
    hop, path, sha256, layout_tree_sha256)

comparison(id, run_id, corpus_item_id, t0_pass, t1, t2_median_pt, t2_p95_pt,
    t3_ssim, font_substitutions[], score)

family(id, family_key(construct_sig, diff_sig), document_classes[], tier,
       fix_class, decision, status, first_seen_run, last_verified_run)

family_doc(family_id, corpus_item_id)

repro(id, family_id, corpus_item_id, minimal_path, synthetic_path, reproduce_cmd)

observation(id, family_id, run_id, renderer_digest, oracle_build, corpus_version,
            result[open|closed|regressed], before_score, after_score)

status: new | isolated | explained | decided | fixed | verified | closed
      | wontfix | invalid
```

`observation` is append-only and carries its own digests because a family is not "fixed"
forever — it is "fixed as of digest X". Without that, the monitoring loop cannot tell
"still broken" from "broken again".

---

## 4. Determinism checklist (oracle)

Every item must pass, or the run aborts:

- [ ] VM image pinned by hash; no background updates
- [ ] Single Word build, version recorded in the run record
- [ ] Fixed locale, region, and measurement units
- [ ] Fixed default printer and driver; printer never changed
- [ ] Fixed installed font set (hashed and recorded)
- [ ] Export→PDF path, not print-to-PDF
- [ ] One document per fresh Word process
- [ ] Double-render comparison: identical layout trees
- [ ] Container versions pinned for every suite renderer (`image@sha256`)
- [ ] Mutation seeds recorded for round-trip runs

---

## 5. Tech choices

| Concern | Choice | Why |
|---|---|---|
| Orchestration | Python 3.12 | Ecosystem for PDF/XML; fastest to iterate |
| PDF layout extraction | PyMuPDF | Gives the span/bbox tree directly |
| Word automation | `pywin32` COM on Windows VM | Only reliable route |
| Run store | DuckDB or SQLite | Single file, queryable, easy to publish |
| Report output | JSON + Markdown, static HTML | script-gateable and shareable |
| Execution | Operator-invoked `make` targets | No CI/CD: runs must be deliberate and recorded |
| Containers | podman (OCI images) | Rootless, daemonless; Docker is absent on the current node |
| XML diff | `lxml` + rsid normalization | Round-trip semantic comparison |

Deliberately avoided: any dependency on a commercial document SDK for the *reference*
side — that would put the oracle under someone else's roadmap.

---

## 6. Repository layout

The repository is split into a public tree (code, docs, config templates) and a
gitignored `private/` tree (corpus, artifacts, run records, real configs). Real documents
carry licence and confidentiality constraints a public repository cannot satisfy, so the
split is enforced by `.gitignore` rather than by convention.

```
ooxml-fidelity-lab/                    PUBLIC
├── README.md
├── GOALS.md
├── DESIGN.md
├── SETUP.md
├── config/
│   ├── oracle.example.yaml            templates only — no machine data
│   ├── renderers.example.yaml
│   └── tolerances.yaml
├── corpus/
│   ├── manifest.example.yaml
│   └── public/                        explicitly publishable fixtures only
├── harness/
│   ├── oracle/                        Word VM driver, determinism checks
│   ├── renderers/                     adapters: soffice, coolwsd, onlyoffice, x2t
│   ├── extract/                       PDF → layout tree
│   ├── compare/                       T0–T3 comparators
│   ├── score/
│   ├── roundtrip/                     mutation matrix + convergence
│   ├── minimize/                      ddmin
│   ├── cluster/
│   ├── synth/                         construct generators
│   └── report/
└── private/                           GITIGNORED
    ├── config/                        real oracle.yaml, renderers.yaml, overrides
    ├── corpus/                        manifest.yaml + items/ (content-addressed)
    ├── artifacts/                     reference + candidate PDFs, layout trees
    ├── runs/                          append-only run store (DuckDB) + records
    ├── reports/                       drafts before publication
    └── vm/                            unattend files, snapshots, licence notes
```

`private/README.md` is the one tracked file inside that tree, so the structure is visible
to contributors without exposing its contents.

---

## 7. Milestones with exit criteria

Phases gate on evidence, not on dates.

**M0 — Smoke**
Render 20 stratified documents through Word and one suite; extract layout trees; produce
one report. *Exit:* a human can read the report and name the worst failure family.

**M1 — Oracle hardened**
Determinism checklist fully green across the 20. *Exit:* double-render identical for
100% of items.

**M2 — Corpus v1**
~500–2000 stratified items with manifest metadata. *Exit:* composition published;
holdout split frozen.

**M3 — Scoring v1**
T0–T3 comparators, per-class aggregates, run store, provenance. *Exit:* two consecutive
runs produce identical scores for identical inputs.

**M4 — Round-trip v1**
Four mutation patterns, convergence detection, semantic XML diff. *Exit:* at least one
document class shows a converged and a non-converged example, both explained.

**M5 — Diagnosis**
ddmin minimizer, clusterer, family records. *Exit:* ≥80% of failures in named families.

**M6 — Utility**
Synthetic generator + at least one upstream issue filed with a minimal repro.
*Exit:* an upstream project acknowledges or fixes a harness-derived repro.

**M7 — Monitoring**
Scheduled runs per upstream release; published release delta. *Exit:* first delta report
correctly flags a known regression.

---

## 8. Open questions

1. **Corpus licensing and redaction.** Real government documents need a policy before
   they enter a publishable corpus. Decide early — it gates M2.
2. **Word licensing for the oracle**, and whether the reference VM can be operated by
   whoever hosts the service long-term.
3. **Who owns the score.** Neutrality is a governance property, not a technical one.
   Foundation host? Public body? This must be settled before publishing numbers.
4. **Which suite is the primary deployment target** — deliberately deferred until the
   harness has produced comparison data. Do not choose from marketing.
5. **Whether to include native-OOXML engines (BetterOffice/Silurus) as renderers.** They
   want a neutral scorer; adding them increases the suite's usefulness and its political
   reach.
6. **Archive angle.** PDF/A and long-term records may deserve their own scoring pass.
   Out of stage 1, but design the schema to allow it.
