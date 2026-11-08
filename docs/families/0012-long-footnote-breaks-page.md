# Family 0012 — a very long footnote breaks the page after its reference

**Status:** decided — annoying, not fixed
**Family key:** word footnote of ~900 words × page break after the reference
**Tier:** T0
**Fix class:** renderer (footnote layout)
**Affected:** 1 document, `bz73977-125317`

---

## Observed

`bz73977-Exampledocx.docx`, 7 pages in Word, 8 in Collabora.

```
Word      p1 572 words, y 57..771
Collab    p1  14 words, y 57..57      ← one line, then nothing
Collab    p2 572 words, y 57..770
```

LibreOffice puts the first sentence on page 1 and breaks the page there. Word
fills the page.

## Mechanism

**Confirmed by measurement.** The first paragraph ends its first line with
`<w:footnoteReference w:id="1"/>`, and that footnote contains **926 words** —
longer than a page. Word splits such a footnote and keeps the body flowing;
LibreOffice appears to refuse, and the body after the reference is pushed to the
next page.

Document facts: 22 paragraphs, 4 footnote entries (two are separators), two of
926 words each, `footnotes.xml` is 28 KB of a 29 KB document. No explicit page
breaks, no frames, no drawings, no tables.

## Why no patch

Footnote layout in `sw` decides how much of a footnote fits on a page and
whether the body continues. Changing it touches pagination for every document
with footnotes, which is a large part of the corpus — the opposite of the
localised changes that have been safe so far. It needs a traced understanding of
`SwFootnoteFrame` before anything is edited.

## Reproduce

```bash
build/instdir-clean/program/soffice --headless --norestore --convert-to pdf \
  --outdir /tmp/out private/corpus/bugzilla/bug73977-Exampledocx.docx
```

Page 1 holds one line; Word's holds 572 words.

## History

| Run | Result |
|---|---|
| run-20261107T203600Z | T0, 7 pages vs 8 |

## Trace: the container grows to 82% of the page

Probe in `SwFootnoteContFrame::Format` (instrumented tree), printing the frame
and print-area heights as the container is formatted for `bz73977`:

```
FTCONT area=0     prt=-269    border=269 fnpage=0
FTCONT area=3239  prt=2970
FTCONT area=4947  prt=4678
FTCONT area=7843  prt=7574
FTCONT area=9254  prt=8985
FTCONT area=10665 prt=10396
FTCONT area=12967 prt=12698
FTCONT area=13784 prt=13515
FTCONT area=0     prt=-269     ← next page
```

The container grows to **13,784 twips of a 16,838-twip A4 page** — 82% — before
the page ends. The body is left with one line, which is exactly what the PDF
shows.

So the mechanism is not "the footnote is dropped" or "the page break is
misplaced": the footnote area is allowed to consume nearly the whole page, and
the body frame is squeezed to whatever is left. Word keeps 572 words on the same
page, which means it caps the footnote area and continues the footnote on the
following page (or pushes the reference), rather than letting the footnote own
the page.

## Decision

**Annoying, not fixed.** Applying the project's own severity rule: all of the
document's text is present in both renders, and 8 pages against 7 is a 1.14x
difference, well inside the 1.3x that counts as unusable. The rules classify
that as annoying — fix if cheap, otherwise adjudicate and report.

A fix is not cheap. The footnote area is allowed to grow until the page is full,
by design (`GrowFrame`: "No check if FixSize since FootnoteContainer are
variable up to their max. height"), and the maximum comes from the page style.
Capping it changes pagination for every document with footnotes, which is a
large part of the corpus, in exchange for removing a one-page difference on one
document.

The verdict page classifies it as annoying with the measurements beside it, so a
reviewer sees it without it competing with real content loss.
