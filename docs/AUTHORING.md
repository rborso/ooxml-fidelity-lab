# Authoring guide — the safe subset

Most fidelity failures are not fixed by changing the software. They are avoided by not
putting the construct in the document. For a closed set of templates, this is the cheapest
lever in the project.

Everything below is based on measured results, not opinion. Where a construct is listed as
unsafe, there is a family record with the evidence.

## Use freely

These round-trip cleanly between Word and Collabora in the current corpus.

| Construct | Notes |
|---|---|
| Body text in Calibri or another metric-compatible font | Carlito substitutes with identical metrics |
| Bold, italic, size changes | |
| Simple tables with explicit borders | Column widths may shift by a few points |
| Lists defined in `word/numbering.xml` | Decimal and bullet both behave |
| Section breaks | Explicit A4 page size and margins |
| Hyperlinks | Internal anchors and external URLs |
| Page headers and footers | Keep fields out of them |
| Tracked insertions (`w:ins`) | Deletions round-trip less reliably |

## Avoid, or expect drift

| Construct | Evidence |
|---|---|
| **Georgia, Calibri Bold variants not in the map** | `0001` — no metric-compatible clone in the container; substituted with NotoSerif |
| **Floating text boxes** | `0002`, `0004` — content dropped, or visited twice |
| **Content controls inside a shape** | `0004` — `w:sdt` inside `w:txbxContent` is skipped |
| **Embedded objects: MathType, ChemDraw, OLE** | `0003` — rendered as picture or text, inconsistently |
| **Table-of-contents fields** | `0005` — regenerated; adds text Word never painted |
| **Legacy binary `.doc`** | `0002` — the importer loses more than the `.docx` path |

## Practical rules for template owners

1. **Fix the font list.** Ship Carlito, Caladea, Gelasio and Liberation on the renderer,
   or use fonts that exist in both worlds. Never leave a template in a font nobody has.
2. **Prefer tables to text boxes.** A bordered table does what a text box does, and it
   round-trips.
3. **Freeze fields before distributing.** A TOC or a date field will differ between any two
   engines that disagree about recalculation.
4. **Keep `.docx` as the interchange format, and convert legacy `.doc` at the source.**
   Do not hand a binary `.doc` to a migration.
5. **Set page size and margins explicitly.** An empty `sectPr` lets Word use Letter and
   Collabora use A4, which changes every line break for the wrong reason.

## What this guide is not

It is not advice to make documents worse. If a construct is essential, the correct response
is the opposite: keep it in the corpus as a regression case and fix the renderer upstream.
The safe subset is for the templates you control and need to ship now.
