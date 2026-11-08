# Family 0012 — a very long footnote breaks the page after its reference

**Status:** isolated, no fix
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
