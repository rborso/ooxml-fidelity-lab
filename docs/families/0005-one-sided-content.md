# Family 0005 — A table-of-contents field is regenerated, adding text Word does not show

**Status:** decided — `adjudicate`
**Family key:** `TOC` field result × content present only in the candidate
**Tier:** T0 (by count only), but not data loss
**Fix class:** `adjudicate`
**Affected:** 1 document (`bz32363-205622`)
**Pinned inputs:** Word `16.0.19127.20860` · `collabora/code@sha256:808410e7…` (26.04.5.2)

---

## Observed

The candidate renders **93 tokens that the reference does not**: `using`, `a`, `character`,
`style`, and so on. Nothing is missing in either direction.

## Mechanism

**Confirmed by inspection.** The document contains one field:

```
TOC \f \o "1-9" \h
```

A table of contents is a *field*, and what Word displays is the cached result stored in the
file. Collabora regenerates it from the headings on load, so it emits entries that were
never in Word's cached result. The upstream issue is titled *"No way to define 2 titles for
a section: full vs short"* — the document is explicitly about which title a TOC should use.

## Decision

**`adjudicate`: do not chase parity.**

Two independent reasons:

1. The reference is showing a *stale cache*. Collabora showing the current headings is not
   wrong; it is arguably more correct.
2. Nobody can win this comparison. Any engine that recalculates fields will differ from any
   engine that does not, and which behaviour a document's author wanted is unknowable from
   the file.

The measurement change that follows: generated field results should not be scored as
content divergence. Either freeze fields in the reference, or exclude TOC/index fields from
the T0 comparison. Until then this document is a known and accepted difference.

## Retest

Not applicable — no fix is intended. If the harness later learns to exclude field-generated
regions, this family should move to `PASS`.

## History

| Run | Renderer digest | Oracle build | Result |
|---|---|---|---|
| run-20261105T194923Z | `sha256:808410e7…` (26.04.5.2) | 16.0.19127.20860 | wontfix — field regeneration |

## Note

`bz36791-46282` was originally grouped here and has been reclassified: it contains no fields
at all, only three text boxes and two drawings. See family 0002.
