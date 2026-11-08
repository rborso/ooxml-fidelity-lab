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

## Controlled experiment (negative)

Zeroing every `wp:extent/@cy` across the family and 20 known-good controls:

| document | Word | unchanged | `cy=1` | extents |
|---|---|---|---|---|
| bz55459-67866 | 15 | 21 | **16** | 25 |
| bz75208-157040 | 174 | 173 | **165** | 108 |
| bz76022-186252 | 2 | 2 | **1** | 2 |
| bz67339-83023 | 3 | 4 | 4 | 9 |
| bz72388-151985 | 3 | 4 | 4 | 2 |
| 14 other family documents | — | unchanged | unchanged | — |
| 20 known-good controls | 1 | 1 | 1 | 0 |

The height effect is real for `bz55459` and does not generalise. On
`bz75208-157040` zeroing the heights moves the page count **further** from
Word's 174, and on `bz76022` it turns a match into a mismatch.

So `anchoredobject` is not one bug with one fix. Either the family is
heterogeneous — several distinct pagination causes wearing the same construct —
or the height is only one contributor and its sign depends on the document.

A patch that added the height to the flow in one case and not the other would
need a condition nobody has evidence for yet. **No patch.**

## History

| Run | Renderer | Result |
|---|---|---|
| run-20261107T045411Z | built-clean 4cce0ff5 | open |

## Splitting the family

Anchor attributes for every family document (first anchor; `behind` = behindDoc,
`n` = number of anchors):

| document | Word pages | n | behind | wrap modes | vFrom | hFrom |
|---|---|---|---|---|---|---|
| bz55459-67866 | 15 | 4 | 0 | none, tight | paragraph | column |
| bz75208-157040 | 174 | 1 | 0 | tight | paragraph | column |
| bz76022-186252 | 2 | 2 | 1 | square, tight | paragraph | column |
| bz67339-83023 | 3 | 9 | 0 | none, square, tight, topAndBottom | page | page |
| bz62613-157544 | 13 | 1 | 0 | none | paragraph | column |
| bz31914-138994 | 7 | 1 | 0 | none | margin | page |
| bz65260-80150 | 1 | 1 | 0 | square | margin | margin |
| bz69864-86699 | 2 | 1 | 1 | none | page | page |
| bz75154-163518 | 3 | 1 | 1 | square | paragraph | margin |

No split follows from these: the two documents whose behaviour differs most
(`bz55459` improves when heights are zeroed, `bz75208` worsens) share
`behindDoc=0`, `paragraph/column` and a tight wrap. The count differs, 4 against
1, and so does the mix of wrap modes, but neither gives a rule.

**Conclusion:** the construct does not identify one bug. Nineteen documents share
a shape construct; the pagination divergence has at least two causes and the
anchor attributes measured here do not separate them. This family is not
patchable from evidence the project currently has, and the honest move is to
leave it `isolated` rather than invent a condition.

## Trace: these are Writer frames, not drawinglayer

`SAL_LOG=+sw.core` on `bz55459` with the instrumented build:

```
sw.core lines: 1,381,382
SwTextBoxHelper::syncProperty: 407 calls
unhandled: InteropGrabBag(66) LineWidth(31) LineStyle(31) FillStyle(31)
           Transformation(30) ParaAdjust(30) CharHeight(30) Graphic(28) ...
unhandled property value: CustomShapeGeometry:TextPreRotateAngle: 0  (4x)
```

So unlike family 0009's VML boxes, these shapes **do** become Writer text
frames and go through the property sync. That means the height question is
answerable in `sw` after all — but no size, auto-height or wrap property appears
among the unhandled ones, so the extra height is not a dropped property.

The only unusual entry is `CustomShapeGeometry:TextPreRotateAngle`, which is
about rotating text inside the shape, not the frame's height.

Next: trace what the frame's height and wrap type are at layout time, rather
than which properties arrive.

## The images are the bigger finding

Comparing what each engine actually draws across the whole document
(`bz55459-67866`, run-20261107T203600Z):

```
Word       15 pages   65 images drawn
Collabora  21 pages   17 images drawn
```

**48 images are missing.** The inline objects declared in the document are
21 (`wp:inline`, all inside table cells, extents around 235x180 pt), and the
drawn set includes banners around 480x54. So the page-count difference this
record has chased for so long may be secondary: the visible defect a user would
report first is that most pictures are not there.

The one banner measured in both engines was 477x40 in Word and 480x54 in
Collabora, so at least one image *is* drawn, just 35% taller.

Next: identify which images are dropped — the `wp:inline` set or the banners —
and whether LibreOffice replaces them with vector shapes. `docs/T0-ANALYSIS.md`
lists this document among 63 T0s with the same structure of evidence.
