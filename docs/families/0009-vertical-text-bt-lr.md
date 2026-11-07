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
