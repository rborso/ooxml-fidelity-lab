# Family 0003 — Embedded objects (equations, OLE) render wrong or not at all

**Status:** explained (three instances, one mechanism)
**Family key:** embedded object (MathType / ChemDraw / formula) × content missing or extra
**Tier:** T0 — data loss
**Fix class:** `renderer`
**Affected:** 4 documents (`bz33590-53915`, `bz45284-57967`, `bz45284-57968`, `bz47240-58329`)
**Pinned inputs:** Word `16.0.19127.20860` · `collabora/code@sha256:808410e7…` (26.04.5.2)

---

## Observed

| Document | Diff | Upstream summary |
|---|---|---|
| `bz33590-53915` | missing 61 tokens | *Add MathType 4+ support for .doc and .docx* |
| `bz45284-57967` | missing 3 tokens | *formulas exported to word are sized incorrectly* |
| `bz45284-57968` | missing 3 tokens | same document, second variant |
| `bz47240-58329` | extra 10 tokens | *Chemdraw OLE objects not detected* |

Content going **both** ways — missing in two, extra in two — is the signature of a
representation mismatch rather than a one-directional conversion loss: each engine renders
the object as text or as a picture, and the other one does not.

## Mechanism

**Hypothesis:** embedded objects are carried as OLE/EMF payloads. Rendering depends on the
fallback representation: MathType and ChemDraw provide both a picture and an equation
object, and the two engines pick different ones. When one picks text, the tokens appear;
when the other picks the picture, they do not.

Confirm by inspecting the object's stored representations in the DOCX (`word/embeddings/`
plus the `mc:AlternateContent` fallback) and checking which branch each engine took.

## Evidence

```
run-20261105T194923Z  bz33590-53915  T0  missing 61
run-20261105T194923Z  bz45284-57967  T0  missing 3
run-20261105T194923Z  bz45284-57968  T0  missing 3
run-20261105T194923Z  bz47240-58329  T0  extra 10
```

## Decision

Upstream renderer defect, and a good candidate for a single upstream report: one mechanism,
four documents, two directions. The `mc:AlternateContent` branch choice is a concrete,
fixable decision.

## Retest

Pending. Pass condition: all four at `PASS` or `T2`, no T0.

## History

| Run | Renderer digest | Oracle build | Result |
|---|---|---|---|
| run-20261105T194923Z | `sha256:808410e7…` (26.04.5.2) | 16.0.19127.20860 | open — 4 documents |
