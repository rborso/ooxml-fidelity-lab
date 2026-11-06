# Family 0004 — Content controls inside a shape are not rendered

**Status:** explained (hypothesis)
**Family key:** `w:sdt` inside `w:txbxContent` × content absent
**Tier:** T0 — data loss
**Fix class:** `renderer`
**Affected:** 1 document (`bz31914-40567`), split into `bz31914-sdt-textbox`
**Documents:** bz31914-sdt-textbox, bz31914-40567
**Pinned inputs:** Word `16.0.19127.20860` · `collabora/code@sha256:808410e7…` (26.04.5.2)

---

## Minimal reproducer

`bz31914-40567` was one document with two independent defects. Splitting its body by
construct isolates this one: a single body-level `w:sdt` wrapping a `w:txbxContent`, which
is 1 of the original 50 body children.

```bash
.venv/bin/python -m harness.cli extract \
  --doc private/corpus/bugzilla/bug31914-ReferenceDocument.docx \
  --out private/corpus/derived/bz31914-sdt-textbox.docx --contains txbxContent
```

That reproducer scores **T0** on its own: Word renders **8 words on 1 page**, Collabora
renders **0 words on 1 page**. The entire text box disappears, so the remaining tables and
paragraphs were never needed to trigger it. Everything else about `bz31914-40567` belongs
to family 0006.

Note on the reproducer: the source text box is followed by an explicit
`<w:br w:type="page"/>`. Once the extraction removed the content after it, Word rendered a
trailing blank page — an artefact of the split, not a property of the document. The
extractor now drops page breaks that have nothing after them, so both sides render one page
and the only remaining difference is the missing text.

The same bug carries the confirmation experiment already: attachment 138994 is the same
document re-saved by Word in 2018, and it scores **ORDER**, not T0 — the text survives.
That is the shortest route to the exact markup difference.

## Observed

8 tokens absent from the whole document, all from the first page's text shape:
`CME`, `Offshore`, `09`, `Accounting`, `Training`, `Exam`.

Upstream summary: *"FILEOPEN: incorrectly formatting 2007 DOCX; missing first page text
shape content with Content Controls"*.

## Mechanism

**Confirmed by experiment.** Two candidate causes were ruled in or out by rendering three
variants of the reproducer through the renderer alone — no Word, no VM:

| Variant | Words rendered |
|---|---|
| original | **0** |
| `sdt` unwrapped, content inlined | **8** |
| `mso-next-textbox` chain removed, `sdt` kept | **0** |

Unwrapping the `sdt` restores every word; removing the VML text-box chaining changes
nothing. So the trigger is the **block-level `w:sdt` inside `w:txbxContent`**, not the
chained shapes.

The importer's shape text-body context accepts `w:p` and `w:tbl` but not `sdt`, so the
tokenizer skips the subtree and the runs never reach the domain mapper. Body-level `sdt`
and text boxes each work; it is the combination that fails.

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
