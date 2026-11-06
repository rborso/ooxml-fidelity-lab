# Family 0006 — Styled tables paginate differently

**Status:** explained
**Family key:** `w:tbl` with `tblLook` conditional formatting × same words, different page assignment
**Tier:** `FLOW`
**Fix class:** `renderer`
**Affected:** `bz31914-styled-tables` (derived from `bz31914-40567`)
**Documents:** bz31914-styled-tables
**Pinned inputs:** Word `16.0.19127.20860` · `collabora/code@sha256:808410e7…` (26.04.5.2)

---

## Observed

```
tier FLOW   pages ref/cand 4 / 4   words ref/cand 432 / 432
pages 2, 3 hold the same words in a different arrangement
```

Every word is present, both documents are four pages, and the word counts match exactly.
Only the page assignment differs: content that sits on page 2 in Word sits on page 3 in
Collabora, and the reverse.

## Mechanism

The tables are sized and styled from their own column grids plus `w:tblLook` conditional
formatting (`0620`, `0660`) and 23 `w:themeColor` references. A difference in row height or
column width moves a table across a page boundary, which reflows everything after it.

This is not content loss and not segmentation — it is pagination.

## A correction worth recording

The first version of this reproducer reported `SEGMENT`, with `250` rendered as `50` + `2`
and 432 words against 452 fragments. That was **an artefact of the split**, not a finding.

Word merges adjacent tables into one. Extracting the seven tables removed the paragraphs
between them, so they became seven consecutive `w:tbl` siblings, Word unified their column
definitions, and the wrapping changed. The extractor now inserts an empty paragraph between
adjacent tables — the same thing a user does by hand — and the word counts match exactly.

**Lesson:** extraction is not free. Removing content can change what the remaining content
means. Any split has to preserve the structural invariants that Word relies on.

## What this family does *not* cover

The visible **border colour and weight** difference is real but unmeasured: the comparator
has no drawing or fill extraction. Any claim about fixing the appearance is unverifiable
until a drawing tier exists.

## Evidence

```
run-20261106T064037Z  bz31914-styled-tables  FLOW 0.60  words 432/432  pages 4/4
```

Earlier, with the merged-table artefact:

```
run-20261106T063236Z  bz31914-styled-tables  SEGMENT 0.70  words 432/452
```

## Reproduce

```bash
.venv/bin/python -m harness.cli extract \
  --doc private/corpus/bugzilla/bug31914-ReferenceDocument.docx \
  --out private/corpus/derived/bz31914-styled-tables.docx --contains tblLook

.venv/bin/python -m harness.cli run --oracle windows \
  --corpus private/corpus/manifest.yaml --only bz31914-styled-tables
```

## History

| Run | Renderer digest | Oracle build | Result |
|---|---|---|---|
| run-20261106T063236Z | `sha256:808410e7…` (26.04.5.2) | 16.0.19127.20860 | SEGMENT (merged-table artefact) |
| run-20261106T064037Z | `sha256:808410e7…` (26.04.5.2) | 16.0.19127.20860 | open — FLOW |
