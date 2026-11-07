# Family 0009 — bottom-to-top vertical text is never laid out

**Status:** isolated, no fix
**Family key:** `layout-flow:vertical` + `mso-layout-flow-alt:bottom-to-top` × empty frame
**Tier:** T0
**Fix class:** renderer

---

## Observed

`bz69175-85548` renders the title "The King's Experience" four times in Word and
once in LibreOffice. `pdfinfo` agrees on the page count, so nothing is
mis-paginated; three text boxes simply draw no text.

The construct is a VML text box with `layout-flow:vertical` and
`mso-layout-flow-alt:bottom-to-top`, which maps to the `BT_LR` writing mode.

## Controlled reproducer

Two minimal documents, identical except for the style string:

| variant | text in PDF |
|---|---|
| `position:absolute;width:200pt;height:60pt` | **1** |
| `…width:60pt;height:200pt;layout-flow:vertical` (TB_RL) | **1** |
| `…layout-flow:vertical;mso-layout-flow-alt:bottom-to-top` (BT_LR) | **0** |

So the failure is specific to `BT_LR`, not to vertical text.

## Where it is not

- **Not the import.** The text is in the ODT and in `--convert-to txt`; it is
  absent only from the PDF. The document model has it.
- **Not the writing-mode property.** Three attempts, each built and measured:
  set the shape's `WritingMode` to `TB_RL` instead of `BT_LR`; set the text
  frame's `TextWritingMode` to `TB_RL`; set neither. All three still render
  nothing.
- `BT_LR` appears in `sw/source/core/doc/textboxhelper.cxx` and in the ODF
  import/export filters, and **nowhere in `sw/source/core/layout/`**. That is
  consistent with a writing mode that is carried through the model but has no
  layout path.

## Why there is no patch

The three attempts above were the plausible property-level fixes and all were
null. What remains is the layout itself: finding why a `BT_LR` frame places no
text needs a trace inside `sw`'s text frame layout, not another property guess.
Writing one now would be the fourth.

Mapping `BT_LR` to `TB_RL` in the importer was also measured on `bz69175`: the
title count went from 11 to 10, i.e. slightly worse, so the property is not the
lever.

## Reproduce

```bash
build/instdir-clean/program/soffice --headless --norestore \
  --convert-to pdf --outdir /tmp/out /tmp/vt-vert.docx   # synthetic, 0 hits
pdftotext /tmp/out/vt-vert.pdf - | grep -c "VERTICAL TEXT"
```

## Correction (same day)

The "renders nothing" reading was measured with `pdftotext | grep -c "VERTICAL
TEXT"`, which returns zero when the renderer breaks the line. pymupdf, the
extractor the harness actually uses, shows the text:

```
vt-horiz   'VERTICAL TEXT'
vt-tbrl    'VERTICAL TEXT'
vt-vert    'VERTICAL \nTEXT'     <- present, wrapped
```

So `BT_LR` does lay the text out. What it does with the corpus document is
**clip** it: in `bz69175`, Word has four copies of "Experience" and LibreOffice
one, while "King's" appears four times in both. The vertical frames cut the
title after the first words — overflow is not painted.

That makes this a different bug from the one the record described: not a missing
writing mode, but a vertical frame that clips its text instead of growing or
wrapping within it. The three property experiments were therefore testing the
wrong property family entirely, which is why all three were null.

The lesson is the same one the minimizer taught: a proxy that does not match the
harness's own extractor produces confident nonsense. `pdftotext` and pymupdf
disagree on wrapped text, and a count of an exact string across a line break is
not a measurement of presence.

## Re-tested with the right oracle

The `BT_LR -> TB_RL` mapping was retried with pymupdf as the measure, since the
earlier "null" result was taken with the broken proxy.

| document | baseline | mapped |
|---|---|---|
| synthetic `vt-vert` | text present, wrapped | `VERTICAL` as one word — vertical layout applied |
| bz69175 | `Experience` 1, `King...` 11 | `Experience` 0, `King...` 10 |

So the mapping helps the synthetic and makes the real document slightly worse.
It fixes the wrapping on a document that already rendered and degrades one that
clipped. Not the fix; reverted.

Iterations spent on this family: 6. Parked per the working rule.

## Instrumented build, first result

`scripts/host/build-dbg.sh` builds a second tree with `--enable-sal-log`, which
turns `SAL_INFO`/`SAL_WARN` on at the release optimisation level. Two attempts
before it failed: `--enable-dbgutil` forces `_GLIBCXX_DEBUG`, which bundled
zxing does not compile under, and `--enable-debug` disables optimisation and
projects a seven-hour build. Final build: **9,934 s (2 h 45 m)**.

Tracing works: a single render produces 18,232 log lines, and
`sax.fastparser` reports element-level detail including `v:textbox`.

First result, and it eliminates the obvious next guess: with a temporary
`SAL_INFO` in `SwTextBoxHelper::syncProperty`, neither the horizontal nor the
vertical variant produces a single line. **The VML text box does not go through
the text-frame property sync at all**, so `TextWritingMode` never reaches it
that way, and the earlier property experiments could not have worked.

Next: trace the drawing-layer shape and text-frame creation for a VML text box,
which is a different path from the one the property code serves.

## Trace: the vertical style never reaches the shape

Probe in `oox/source/vml/vmlshape.cxx` at the point where the writing mode is
computed, run against both synthetic variants:

```
vt-horiz   FBTLR flow= alt=        mode=0
vt-vert    FBTLR flow= alt=        mode=0
```

`flow` is `TextBox::maLayoutFlow`, which `vmltextboxcontext.cxx:220` sets from
the `layout-flow` style property. It is **empty for both**, so the writing mode
is `LR_TB` in both cases and the vertical handling never runs.

That also explains the earlier confusion: `vt-tbrl` appeared to render on one
line only because clipping does not remove text from the PDF content stream —
pymupdf still extracts clipped glyphs. All three variants were laid out the same
way, horizontally, in a 60 pt box.

So the family's real defect is one step earlier than every hypothesis so far:
the `layout-flow` style is parsed into a `TextBox` object that the shape
conversion does not read. Either two different `TextBox` instances are involved
or the parse happens after the shape is built. That is the next thing to trace,
and it is now a named object rather than a writing-mode theory.

## Probes reverted

The instrumented tree is back to a clean build; the probes were temporary.

## The reproducer was wrong, twice

`layout-flow` lives on the `<v:textbox>` element in Word's output. My synthetic
put it on `<v:rect>`, so the probe correctly reported an empty `maLayoutFlow` -
the document never set it. Rebuilt with the style where Word puts it:

| variant | `VERTICAL` | `TEXT` |
|---|---|---|
| no vertical style | 1 | 1 |
| `layout-flow:vertical` (TB_RL) | 1 | 1 |
| `…;mso-layout-flow-alt:bottom-to-top` (BT_LR) | 1 | 1 |

**All three render.** The writing mode is applied and `BT_LR` works. Every
writing-mode theory in this record is therefore dead, including the one the last
trace appeared to confirm.

`getTextBox()` returns `maShapeModel.mxTextBox` - the same object `TextBoxContext`
fills - so the two-object theory is dead as well.

## What is left

The corpus document's three vertical frames clip their titles. `mso-fit-shape-to-
text` is absent (0 occurrences) and zeroing the textbox inset changes nothing
(`Experience` 0 and `King` 10 in both). So neither auto-height nor inset margins
explain it, and the remaining difference is geometry between a 44 pt frame and
the text placed in it.

Two invalid reproducers in one family is the reason this has taken so long: each
one "confirmed" a mechanism that did not exist in the real document.

## Trace on the real document: wrong subsystem

Probe in `SwTextFrame::Format_` printing writing mode and frame print area, run
on `bz69175`:

```
FFRM vert=0 swapped=0 area=9901x0  text=[Please complete this application form if]
FFRM vert=0 swapped=0 area=10200x0 text=[King's Global Award]
FFRM vert=0 swapped=0 area=5024x0  text=[King's student ID no.:]
```

The probe fires for body paragraphs only. **The vertical text box content never
reaches `SwTextFrame`** — it is laid out by drawinglayer on the shape, not by
sw's text layout. So every frame-geometry question asked of `sw` here was asked
of the wrong subsystem.

That also explains why `SwTextBoxHelper::syncProperty` is never called for these
shapes: they are drawing objects, not Writer frames.

The remaining work is in `svx`/`drawinglayer` text layout for a rotated fixed-size
shape with `layout-flow:vertical`. Nothing in `sw` will answer it.
