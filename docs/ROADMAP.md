# Roadmap

Twenty steps to reach the goal: make "will our documents work?" answerable with a number,
before anyone has to risk a pilot on it.

Ordered so each step builds on the last. Every step names its exit criterion and the test
that proves it. Nothing is "done" until the test exists and passes.

Status key: `done` · `partial` · `blocked` (needs an external resource)

---

## A. Measurement integrity

Volume on a wrong metric is waste, so correctness first.

| # | Step | Exit criterion | Test | Status |
|---|---|---|---|---|
| 1 | Per-document tolerances: a manifest item may declare `allow_missing` / `allow_extra`, downgrading T0 to `FIELD` | A tagged document scores `FIELD`, an untagged one still `T0` | `test_allow_extra_downgrades_to_field`, `test_extra_without_tolerance_is_t0` | done |
| 2 | Cross-check the PDF extractor against a second text engine (poppler `pdftotext`) | Token agreement ≥99% on ≥50 documents, disagreements listed | `crosscheck` command prints agreement and exits non-zero under threshold | done |
| 3 | ddmin minimiser over the document body, with a pluggable render predicate | A known-failing document reduces to ≤10 body elements while still failing | `test_ddmin_reduces_body`, plus a recorded reduction on a real document | done |
| 4 | Automatic clustering by OOXML construct signature | Every failing document lands in a named cluster; cluster ids stable across runs | `test_signature_is_stable`, `cluster` command output | done |

## B. Oracle

| # | Step | Exit criterion | Test | Status |
|---|---|---|---|---|
| 5 | Named oracle builds and a Word-versus-Word drift command | Two oracles compared; drift reported per document class | `test_drift_between_runs` (stub oracles) | done |
| 6 | Confirmation experiments for the open T0s | Each open family has a recorded experiment and a verdict | family records updated with verdicts | done |

## C. Corpus

| # | Step | Exit criterion | Test | Status |
|---|---|---|---|---|
| 7 | Licence and redaction policy, enforced by `check --strict` | Missing licence fails the check; unpublishable items are refused | `test_strict_licence`, policy doc reviewed | done |
| 8 | Synthetic construct suite, one per Word feature | ≥12 constructs, each a valid DOCX that renders | `test_all_constructs_build`, `test_constructs_render` | done |
| 9 | Grow the tracker corpus past 60 documents, paginated fetch | ≥60 documents on disk, manifest valid | `fetch --pages 3` then `check` | done |
| 10 | Frozen holdout split | Manifest hash of the holdout recorded; runs honour `--split` | `test_holdout_frozen`, `test_split_filter` | done |

## D. Coverage

| # | Step | Exit criterion | Test | Status |
|---|---|---|---|---|
| 11 | OnlyOffice as a second renderer | Adapter renders or reports a precise unavailable reason | `test_onlyoffice_adapter_contract` | done |
| 12 | Round-trip testing with convergence detection | Four mutation patterns run; converged vs drifting reported | `test_convergence_detection`, `test_roundtrip_patterns` | done |
| 13 | Archival checks: fonts embedded, text extractable, page count stable | Every corpus document scored; failures named | `test_archive_checks` | done |

## E. Delivery

| # | Step | Exit criterion | Test | Status |
|---|---|---|---|---|
| 14 | Per-class usage weighting | Score per document class, weights from config | `test_class_weights` | done |
| 15 | Release delta between two runs | Per-document and per-class change reported | `test_release_delta` | done |
| 16 | Published baseline report | Site shows baseline: per-class scores, families, corpus composition | site build includes `baseline.html` | done |
| 17 | Packaging for another organisation | A stranger can run the harness from the runbook alone | `docs/RUNBOOK.md` + `scripts/host/bootstrap.sh` | done |
| 18 | Ownership and hosting of the score | Written decision framework, not a code change | `docs/GOVERNANCE.md` | done |
| 19 | Upstream reproducers prepared | Issues drafted with repro, evidence, and expected behaviour | `docs/upstream/*.md` | done |
| 20 | Safe-subset authoring guide | Constructs that round-trip cleanly, with the failing ones named | `docs/AUTHORING.md` | done |

---

## Explicitly out of scope

- 100% fidelity. Unreachable: layout is an algorithm, not a spec.
- Converging two engines on pixels. Knowledge transfers, code does not.
- Replacing Microsoft Office. This is a switching-cost reducer.
- Filing on public trackers on the operator's behalf. Drafts only.
