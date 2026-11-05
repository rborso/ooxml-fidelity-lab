# harness/

Implementation of the pipeline described in [DESIGN.md](../DESIGN.md). Empty at pre-M0.

## Planned modules

| Module | Responsibility |
|---|---|
| `oracle/` | VM driver, job queue over the shared folder, determinism checks |
| `renderers/` | Adapters: `soffice`, `coolwsd`, `onlyoffice`, `x2t` |
| `extract/` | PDF → normalized layout tree (spans, bboxes, geometry) |
| `compare/` | T0–T3 comparators, font substitution report |
| `score/` | Per-document and per-class aggregation, release deltas |
| `roundtrip/` | Mutation matrix, convergence detection, semantic XML diff |
| `minimize/` | ddmin over zip parts and `document.xml` |
| `cluster/` | Failure families by construct signature + diff signature |
| `synth/` | Single-construct document generators |
| `report/` | JSON + Markdown output |

## Build order

Do not write these in parallel. The sequence is load-bearing:

1. Oracle driver + determinism gate (SETUP.md §10) — **stop here until green**
2. Extractor + T0/T1 comparators
3. One renderer adapter, 20 documents, one report
4. Corpus scaling, T2/T3
5. Minimizer → clusterer → synthetic generator

The failure mode to avoid: a complete framework that scores the wrong thing.
