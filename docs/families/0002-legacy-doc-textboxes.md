# Family 0002 — Text boxes in legacy .doc are dropped

**Status:** explained (hypothesis confirmed by the document's own bug report)
**Family key:** floating text box (`w:txbxContent` / `fSpec`) in a `.doc` file × content absent
**Tier:** T0 — data loss
**Fix class:** `renderer`
**Affected:** 1 document so far (`bz34722-43806`), plus the mirror case `bz36791-46282`
**Documents:** bz34722-43806, bz36791-46282
**Pinned inputs:** Word `16.0.19127.20860` · `collabora/code@sha256:808410e7…` (26.04.5.2)

---

## Related

`bz36791-46282` is the mirror image: a `.docx` with three text boxes and two drawings, where
the **candidate emits 7 extra tokens** rather than dropping them. Same construct family,
opposite direction — which strongly suggests the problem is not "text boxes are unsupported"
but "text boxes are traversed inconsistently", sometimes skipped and sometimes visited twice
or expanded.

## Observed

**139 tokens absent from the whole rendered document** — not moved between pages, not
reordered. Gone. Samples: `Lapo`, `Nr`, `UAB`, `RABEN`, `LIETUVA`.

The upstream report says the same thing in its own words: *"FILEOPEN: Text boxes are not
shown in generated .doc documents"*.

## Mechanism

**Hypothesis, strongly supported:** the legacy binary `.doc` importer does not surface
floating text boxes, so their content never enters the document model and therefore never
reaches the layout. The `.docx` path handles text boxes; this is specific to the binary
format's frame records.

Worth confirming by re-saving the same document as `.docx` in Word and re-running: if the
tokens reappear, the importer is the boundary and the model is fine.

## Evidence

```
run-20261105T194923Z  bz34722-43806  T0  missing 139  pages ref=1 cand=1
```

Page counts match, so this is not pagination — content simply is not in the candidate PDF.

## Reproduce

```bash
make run-oracle                     # full corpus
.venv/bin/python -m harness.cli run --oracle windows \
  --corpus private/corpus/manifest.yaml --limit 20
```

## Decision

Upstream renderer defect. Do not patch around it in the harness: the corpus entry is the
regression test. File the minimised reproducer upstream with the token list as evidence.

## Retest

Pending a renderer fix. Pass condition: `missing 0`, tier at least `FLOW`.

## History

| Run | Renderer digest | Oracle build | Result |
|---|---|---|---|
| run-20261105T194923Z | `sha256:808410e7…` (26.04.5.2) | 16.0.19127.20860 | open — 139 tokens missing |
