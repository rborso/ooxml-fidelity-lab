# Pixel-to-pixel comparison: parked

**Status:** parked 2026-11-06. Code retained, disabled by default, re-enable with
`--pixels`. Nothing was deleted: `harness/pixels.py` and `tests/test_pixels.py` are intact.

## What was built

Both PDFs rasterised to grayscale at 72 dpi (1 pt = 1 px) and compared per page, giving
a changed fraction, the bounding box of the changed region, a density value and a
`diffuse`/`concentrated` classification, plus a red-on-grey heatmap PNG for a human.
Dependency-free: `pdftoppm` emits PGM, a small parser reads it, zlib writes the PNG.

## What was measured

Noise floor, same binary rendering the same document twice: **0.0000 on every page.**
The metric itself is sound.

Corpus, built-clean against Word, 321 documents:

| tier | median | p90 | max |
|---|---|---|---|
| PASS | 0.49% | 1.61% | 7.63% |
| T2 | 0.54% | 3.79% | 9.55% |
| T2-fonts | 1.01% | 16.16% | 36.36% |
| T1 | 6.84% | 13.92% | 100% |
| FLOW | 13.25% | 24.12% | 100% |

Pattern classification: **258 diffuse, 62 concentrated, 1 none.** The only three
text-PASS documents above the 2% band were all diffuse, i.e. glyph rasterisation rather
than layout. The concentrated set was where the real differences were — `bz67339-83023`
at 88.9%, `bz37315-46861` at 36.4%, the residence-permit forms at ~25%.

## Why it is parked

The two engines never rasterise identically. Hinting, anti-aliasing, glyph outlines and
kerning rounding differ even for a metric-compatible substitution, so a pixel fraction
measures the renderer's typography as much as the document's layout. Reporting that as
`visible` or `major` reads as a fidelity grade and is not one: three documents marked
"visibly different" were typography, and the documents that really broke were already
caught by T0, T1 and FLOW.

It also costs: roughly five minutes per lane, and an hour of CPU per site rebuild when
heatmaps are generated.

The classification was the useful part. The score was not.

## What has to change before re-enabling

1. **Mask the text.** Both PDFs carry a text layer with a box per word. Blank those boxes
   on both sides and diff only the remainder. What survives is exactly what the text
   comparator cannot see: borders and their colours, cell and paragraph shading, images,
   vector shapes. Glyph shape and hinting disappear inside the masks.
2. **Give layout its own tier instead of borrowing pixels for it.** Match blocks by their
   text, compare matched boxes with a tolerance in points (2 pt is a fifth of a line
   height), and report `moved` / `missing` / `added` with the distance and the page. That
   is "same pages, same layout, same text in the same place", and it is tolerance-based
   by construction.
3. **Drop the grade vocabulary.** `visible` / `major` imply fidelity. Report regions:
   `non-text 0.4% of page, centre-right`.
4. **Re-calibrate from scratch.** The bands above were derived from unmasked diffs and are
   meaningless for masked ones. The zero floor and every boundary must be re-measured.

## Known limitation of the proposed fix

Masking a word's box also hides whatever is painted behind it: a shaded cell or a rule
running under text is removed with the glyphs. Mitigation is to diff a ring around each
mask rather than the whole box, and to state the residual blind spot in the report rather
than claim coverage.

## What is still worth keeping from this work

- `density` and the `diffuse` / `concentrated` split are sound and reusable for the masked
  version.
- The PGM parser and PNG encoder are dependency-free and are what the heatmap view needs.
- The heatmap rendering itself is fine; it was the scoring use that was wrong.
