# Family 0007 — a floating shape adds its height to the text flow

**Status:** isolated
**Family key:** `wps:wsp` / `w:pict` anchored object × extra page per shape
**Tier:** T0 (via page count), then FLOW
**Fix class:** renderer
**Affected:** 19 documents contain the construct; 11 are T0

---

## Observed

`bz55459-67866` renders as **21 pages** in LibreOffice and **15** in Word. On the
shared pages LibreOffice holds less text:

| page | Word tokens | LibreOffice tokens |
|---|---|---|
| 6 | 373 | 234 |
| 9 | 325 | 192 |
| 10 | 340 | 190 |
| 11 | 326 | 191 |

The remainder spills onto pages 16–21. The text itself is present: the document's
repeated heading appears 37 times in Word's PDF and 21 times here — fewer
occurrences, not fewer characters.

## Evidence

Four renders of the same document, measured by page count:

| change | pages |
|---|---|
| none | 21 |
| all `w:drawing` / `w:pict` removed (29 objects) | **16** |
| every `wp:extent` `cy` set to 1 | **16** |
| every `wp:anchor` `behindDoc` set to 1 | 21 |

Deleting the shapes and zeroing their height do the same thing. Setting
`behindDoc` does nothing. So the flow is inflated by the anchored objects'
**extent**, not by their z-order or their wrap mode as such.

Word renders the same page count with the same shapes, so this is not a document
defect: it is how the anchored object is added to the layout.

## Mechanism

**Confirmed:** the shape's height reaches the vertical flow. Zeroing `cy` is
enough to remove five of the six extra pages.

**Hypothesis:** the anchor is treated as occupying space in its paragraph rather
than floating over it. The remaining one-page difference (16 vs 15) is separate
and not yet isolated.

## Reproduce

```bash
build/instdir-clean/program/soffice --headless --norestore \
  --convert-to pdf --outdir /tmp/out \
  private/corpus/bugzilla/bug55459-hagilboa_yehudi_800000_hesegim_0811.docx
pdfinfo /tmp/out/*.pdf | grep Pages        # 21, Word says 15
```

Zero the heights (`wp:extent/@cy=1` on all 25 extents) and it renders 16.

## Decision

Not decided. The next step is to find where the anchored object's height is added
to the frame: `sw/source/core/layout/anchoredobject.cxx` and `flowfrm.cxx` both
branch on the surround mode, and `flycnt.cxx` rewrites `WrapTextMode_NONE` to
`THROUGH`. A fix there is a layout change and needs the whole corpus to judge,
not one document.

## Retest

| Metric | Before | After |
|---|---|---|
| Family documents failing | 11 | — |
| Corpus-wide new failures | — | — |

## History

| Run | Renderer | Result |
|---|---|---|
| run-20261107T045411Z | built-clean 4cce0ff5 | open |
