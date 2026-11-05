# Family 0004 — Content controls inside a shape are not rendered

**Status:** explained (hypothesis)
**Family key:** `w:sdt` inside `w:txbxContent` × content absent
**Tier:** T0 — data loss
**Fix class:** `renderer`
**Affected:** 1 document (`bz31914-40567`)
**Pinned inputs:** Word `16.0.19127.20860` · `collabora/code@sha256:808410e7…` (26.04.5.2)

---

## Observed

8 tokens absent from the whole document, all from the first page's text shape:
`CME`, `Offshore`, `09`, `Accounting`, `Training`, `Exam`.

Upstream summary: *"FILEOPEN: incorrectly formatting 2007 DOCX; missing first page text
shape content with Content Controls"*.

## Mechanism

**Hypothesis:** structured document tags (`w:sdt`) nested inside a floating text box are
skipped by the importer. Either the shape content is walked without descending into `sdt`,
or the `sdt` is dropped when it appears outside the body-level content flow.

This is a nested-construct bug: text boxes work (family 0002 is the `.doc` path, not this),
and content controls work at body level. It is the combination.

## Evidence

```
run-20261105T194923Z  bz31914-40567  T0  missing 8
```

## Reproduce

```bash
.venv/bin/python -m harness.cli run --oracle windows \
  --corpus private/corpus/manifest.yaml --limit 20
```

Then minimise: strip the document to the single text box containing the content control.

## Decision

Upstream renderer defect. Worth a minimal synthetic construct too — `w:txbxContent`
wrapping `w:sdt` — so the regression test does not depend on a third-party document.

## Retest

Pending. Pass condition: `missing 0`.

## History

| Run | Renderer digest | Oracle build | Result |
|---|---|---|---|
| run-20261105T194923Z | `sha256:808410e7…` (26.04.5.2) | 16.0.19127.20860 | open — 8 tokens missing |
