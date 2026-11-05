# OOXML Fidelity Lab — Goals

## One sentence

A versioned, corpus-driven differential harness that scores office-suite rendering and
round-trip fidelity against a pinned Microsoft Word, per document class, across new
documents and new releases — producing tiered scores, minimized reproducers, and failure
clusters instead of opinions.

---

## 1. The problem

### 1.1 The question is currently unanswerable

"Will our documents work if we move off Microsoft Office?" can only be answered today by
running a pilot. There is no neutral, repeatable measurement. Vendors publish marketing;
bug trackers hold individual anecdotes; feature-comparison wikis describe capabilities, not
fidelity.

### 1.2 The pilot is a political artifact, not a measurement

Pilots can be cancelled, defunded, reorganized, or orphaned. Denmark's Ministry of
Digitization pilot was not killed by font substitution or track changes — Collabora states
those tickets were resolved. It died because a government reorganisation abolished the
ministry and an election interrupted the evaluation. No formal assessment was ever
completed, so the record now says "failed" when the truth is "unfinished."

**Corollary: if the only way to produce evidence is a pilot, the evidence dies with the
pilot.** The measurement must exist before, and independently of, the political project.

### 1.3 No neutral measurement layer exists

- LibreOffice, Collabora, OnlyOffice and the new Rust/WASM engines all have internal
  test suites. These are implementation-internal property assertions, not cross-engine
  render comparison, not a public corpus, and not a published score.
- No vendor can credibly certify its own fidelity.
- The closest precedent is **veraPDF**: EU PREFORMA-funded (2014–2017), vendor-independent,
  permissively licensed, now maintained by the Open Preservation Foundation. It became the
  authority for PDF/A and outlived its funders.

**This project is veraPDF for OOXML rendering** — with one essential difference: PDF/A is
fully specified, so validation is possible. Word layout is *not* specified, so this
requires a differential oracle rather than a validator. That is the novel, hard, and
currently unbuilt part.

---

## 2. In scope / out of scope

| In scope | Out of scope |
|---|---|
| Differential rendering scores vs pinned Word | Writing or forking an office engine |
| Round-trip degradation and convergence | A migration playbook or training material |
| Minimized reproducers for upstream | Bug-for-bug compatibility patches |
| Failure clustering into families | Vendor benchmarking or marketing |
| Synthetic single-construct regression cases | Real-time collaboration testing |
| Per-release regression tracking | Spreadsheet/slides fidelity (phase 3, maybe) |

---

## 3. Users and what each gets

| User | What they get |
|---|---|
| CIO / procurement | A citable number: "document class X scores N.N against pinned Word, three known families" |
| Migration team | A ranked work queue of failure families, not a pile of broken files |
| Upstream projects | Minimized, labelled reproducers + a permanent regression case |
| Policymaker / funder | Evidence that survives the project that produced it |
| Archives / records | A repeatability and preservation signal for long-lived document classes |

---

## 4. Success criteria

Measured per phase; each phase must be *done* before the next starts.

### Phase 1 — oracle
- A pinned Word VM renders the corpus to PDF **bit-stably** across repeated runs.
- Determinism verified: same document rendered twice yields identical layout trees.

### Phase 2 — measurement
- End-to-end pipeline runs to completion from a single operator command, with no manual
  step between ingest and report.
- Every score is traceable to (corpus item, software version, Word build, harness version).
- Tiered scores computed for ≥1 open suite against pinned Word.

### Phase 3 — diagnosis
- ≥80% of failing documents reduced to a minimal reproducer.
- Failures grouped into named families, each with a construct signature and a diff
  signature.
- Every family carries a fix class. `adjudicate` (Word is wrong) and `invalid` (harness
  artifact) are recorded outcomes, not silently dropped.

### Phase 4 — utility
- At least one upstream project accepts a fix or regression test derived from a harness
  reproducer.
- Every verified fix ships with a synthetic regression case that failed before it and
  passes after, and a corpus-wide sweep shows no new failures.
- A published report with per-class scores and one Markdown page per known family.

### Phase 5 — monitoring
- A single operator command re-runs the full corpus against a new release. No CI/CD: the
  run is a script invocation with pinned inputs, not an automated pipeline.
- Publishes a release delta: what regressed, what improved.

### Standing qualitative success
A procurement or policy conversation can cite the scoreboard instead of commissioning a
pilot. **This is the actual product.**

---

## 5. Non-goals

Explicitly **not** attempting:

1. **100% fidelity.** Unreachable — layout is an algorithm, not a spec, and font
   availability is environmental. Chasing it is how projects die.
2. **Converging two engines.** Knowledge transfers; code does not. Pick one to deploy,
   keep the other as a disagreement detector.
3. **Proving Microsoft wrong or right.** The harness reports differences; adjudication is a
   human policy decision per case.
4. **Replacing Microsoft Office.** This is a switching-cost reducer, not a migration.
5. **A general document-diff tool.** Text/semantic diff exists (`prosediff`, Docxodus).
   This measures *rendered layout*, which those do not.

---

## 6. Scope decisions

- **Primary format:** DOCX. Secondary: ODT (cross-format churn). Output: PDF.
- **Reference:** one pinned Microsoft Word build on one pinned Windows VM. Never floating.
- **Suites under test:** at minimum one of Collabora Online / OnlyOffice Docs;
  optionally LibreOffice desktop and native-OOXML engines.
- **Document classes:** government case documents, ministry templates, inter-agency
  correspondence. Deliberately narrow at first — the corpus must be representative of a
  population, not of "all documents."
- **Stage 1 excludes:** spreadsheets, presentations, macros/VBA, real-time co-editing.

---

## 7. The honest claim

This does **not** close the Microsoft monopoly gap. The binding constraints are ecosystem
coupling (identity, collaboration, compliance), bundled economics, inter-organizational
coordination, skill stock, and political durability. Fidelity is one of ~five constraints,
and it is the *excuse* more often than the cause.

What this **does** do:

- Removes the standard objection, by replacing "it doesn't work" with a number.
- Moves the answer earlier — measurable *before* a politically exposed pilot.
- Produces a public good: an interop suite where none exists, so every subsequent
  migration in every country gets cheaper.
- Makes the gap legible to vendors, whom procurement can then cite it against.

Historically, the technical gap has been closable for a decade. What correlates with
successful migrations is mandate scope plus political durability — Schleswig-Holstein,
Austrian Armed Forces, the French Gendarmerie. Munich's partial reversal was political,
not technical. Plan accordingly, and never oversell.

---

## 8. Risks

| Risk | Mitigation |
|---|---|
| Word oracle requires a licensed Word + Windows VM | Budget it explicitly; it is a test oracle, not production. Document the irony. |
| Oracle non-determinism makes scores incomparable | Enforce the determinism checklist; fail the run if repeated renders differ. |
| Corpus unrepresentative | Stratify; re-baseline against real usage; publish the corpus composition. |
| Upstream indifference to patch-queue approach | Lead with reproducers and regression tests; make their job easy. |
| Native-OOXML engines make suites irrelevant | Their claims still need an independent oracle; archives still need a validator. |
| "97% is good enough" political argument | Score per document class with named known-failures, never a single global number. |
| Funding dies after the first report | Position as continuous monitoring; release deltas are the recurring product. |
| Scope creep into spreadsheets/slides | Hard phase gate; stage 1 is DOCX only. |

---

## 9. Definition of the project in one line

> Make the document-fidelity question answerable with a number, before anyone has to risk a
> pilot on it.
