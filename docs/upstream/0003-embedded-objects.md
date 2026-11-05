# DRAFT — not filed

**Component:** Writer / embedded objects
**Summary:** Embedded objects (MathType, ChemDraw, OLE) render inconsistently — content
appears as text in one engine and as a picture, or not at all, in the other

## Affected documents

| Document | Difference | Tracker summary |
|---|---|---|
| `bz33590-53915` | 61 tokens missing | *Add MathType 4+ support for .doc and .docx* |
| `bz45284-57967` | 3 tokens missing | *formulas exported to word are sized incorrectly* |
| `bz45284-57968` | 3 tokens missing | same document, second variant |
| `bz47240-58329` | 10 tokens extra | *Chemdraw OLE objects not detected* |

## Steps to reproduce

1. Open each document.
2. Export to PDF.
3. Compare the text layer with Word's export.

## Expected

The fallback representation chosen on import should be the same one Word used, so the
visible object and its text are equivalent.

## Actual

The direction of the difference flips between documents — missing in two, extra in two.
That is the signature of an `mc:AlternateContent` branch choice, not simple conversion
loss: one engine takes the picture branch, the other takes the text branch.

## Suggested investigation

Dump the object's stored representations (`word/embeddings/`, plus the
`mc:AlternateContent` fallback) and record which branch each engine selected.

## Environment

- Collabora Office 26.04.5.2 (`collabora/code@sha256:808410e7…`)
- Microsoft Word 16.0.19127.20860

## Evidence

```
run-20261105T194923Z  bz33590-53915  T0  missing 61
run-20261105T194923Z  bz45284-57967  T0  missing 3
run-20261105T194923Z  bz45284-57968  T0  missing 3
run-20261105T194923Z  bz47240-58329  T0  extra 10
```
