# Upstream filings — drafts

Two patches are verified in the lab with zero corpus regressions. These are the
reports to attach them to. Posting is a decision, not a writing task.

---

## 1. Content control in a VML text box is dropped

**Product:** LibreOffice Writer (also affects Collabora Online, same core)
**Component:** filters and storage · **Version:** 26.2.8.0 (commit `4cce0ff5`)
**Attachment:** `bz31914-sdt-textbox.docx` (already public, Bugzilla 31914
context), plus `fix.patch`

### Summary

Text inside a content control (`w:sdt`) that sits in a VML text box
(`v:textbox > w:txbxContent`) inside a `.docx` is not imported. Word renders the
cached content; LibreOffice renders an empty text box.

### Steps to reproduce

1. Open `bz31914-sdt-textbox.docx` in Writer.
2. Compare with Word: the shape contains "CME Offshore", Writer shows nothing.
3. `--convert-to odt` and inspect `content.xml`: the text is absent from the
   document model, so the loss is at import, not layout.

### Cause

`oox/source/vml/vmltextboxcontext.cxx`, `TextBoxContext::onCreateContext()`:

```cpp
case W_TOKEN(txbxContent):
    if (nElement == W_TOKEN(p)) return this;
break;
```

Only `w:p` is accepted as a child of `w:txbxContent`. An `w:sdt` returns
`nullptr` and the whole subtree is never parsed. The `sdt` and `sdtContent`
cases already in the same switch handle the inside of the control.

### Proposed fix

```diff
         case W_TOKEN(txbxContent):
-            if (nElement == W_TOKEN(p)) return this;
+            if (nElement == W_TOKEN(p) || nElement == W_TOKEN(sdt))
+                return this;
         break;
```

Measured: the lost token renders once with the patch, zero times without, same
binary otherwise. Corpus of 325 documents: 2 improved, 0 degraded.

---

## 2. A floating table with an anchor and no position lands outside the print area

**Product:** LibreOffice Writer · **Component:** filters and storage
**Version:** 26.2.8.0 (commit `4cce0ff5`)
**Attachment:** `hu-gov-9.21 … k-ntes_tev-kenys-g_folytat-sa_HU.docx`
(reproduced from a public Hungarian government form), plus `fix.patch`

### Summary

A table with `<w:tblpPr>` naming `horzAnchor` but neither `tblpXSpec` nor
`tblpX` is imported with `HoriOrient = NONE` and position 0. Writer places it
outside the printable area — in the observed document at x=3 pt on a page whose
margin is 55 pt — where Word aligns it to the anchor.

### Steps to reproduce

1. Open the attachment; item "4." and everything after it sits against the page
   edge instead of the margin.
2. Compare with Word: the same text is at the margin.

### Cause

`sw/source/writerfilter/dmapper/TablePositionHandler.cxx`:

```cpp
sal_Int16 nHoriOrient = text::HoriOrientation::NONE;
if (m_aXSpec == "center") …
```

With no `tblpXSpec` the orientation stays `NONE`, and the position is written as
`m_nX`, which is 0. OOXML permits exactly this combination.

### Proposed fix

Treat a missing spec with an anchor as left-aligned to that anchor:

```diff
+    if (m_aXSpec.isEmpty() && m_nX == 0 && !m_aHorzAnchor.isEmpty())
+        nHoriOrient = text::HoriOrientation::LEFT;
+    else if (m_aXSpec == "center")
-    if (m_aXSpec == "center")
```

and set `HoriOrientPosition` to 0 for that case instead of `m_nX`.

Measured: `4.` moves from x=3 to x=56, matching Word; the document's placement
findings drop from 37 to 1. Corpus: 3 improved, 0 degraded.

---

## What both filings share

- a minimal, public reproducer
- before/after measured on the rendered PDF, not on an internal model
- the corpus result: improved / degraded / unchanged, with run ids
- a revert documented in the lab (`patches/0001`, `patches/0003`)

## Still to decide

- whether to file as two bugs or one (they are unrelated modules)
- whether to attach the corpus evidence, which names other public documents
