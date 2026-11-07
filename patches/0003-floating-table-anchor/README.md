# Patch 0003 — a floating table with an anchor but no position

**Status:** verified
**Family:** 0010
**Upstream component:** writerfilter

---

## The change

`sw/source/writerfilter/dmapper/TablePositionHandler.cxx`:

```diff
     sal_Int16 nHoriOrient = text::HoriOrientation::NONE;
+    // A floating table may name an anchor and give no tblpXSpec and no tblpX
+    // at all. Left as NONE with position 0 it lands outside the print area;
+    // Word aligns it to the anchor. Treat the missing spec as left-aligned.
+    if (m_aXSpec.isEmpty() && m_nX == 0 && !m_aHorzAnchor.isEmpty())
+        nHoriOrient = text::HoriOrientation::LEFT;
+    else if (m_aXSpec == "center")
-    if (m_aXSpec == "center")
```

and the position assignment follows the orientation instead of always using
`m_nX`:

```diff
-    aFrameProperties[u"HoriOrientPosition"_ustr]
-        <<= ConversionHelper::convertTwipToMm100_Limited(m_nX);
+    if (nHoriOrient == text::HoriOrientation::LEFT)
+        aFrameProperties[u"HoriOrientPosition"_ustr] <<= sal_Int32(0);
+    else
+        aFrameProperties[u"HoriOrientPosition"_ustr]
+            <<= ConversionHelper::convertTwipToMm100_Limited(m_nX);
```

## Why

OOXML allows `<w:tblpPr>` with `horzAnchor` and no `tblpXSpec`/`tblpX`. The
handler leaves `nHoriOrient` at `NONE` with position 0, which places the table
outside the print area. Word aligns such a table to its anchor.

Measured on `hu-gov-9.21 … k-ntes_tev-kenys-g_folytat-sa_HU`:

| | `4.` x | placement findings |
|---|---|---|
| clean | 3 | 37 (36 displaced, 1 outside) |
| patched | **56** | 1 (outside) |

Word puts it at 56.

## Corpus

```
compared=325 improved=3 degraded=0 unchanged=322
  bz31914-40567      T0 -> T1    (patch 0001)
  bz31914-sdt-textbox T0 -> T2   (patch 0001)
  hu-gov-9.15 …      T0 -> ORDER (this patch)
```

mean 0.5429 → 0.5475, T0 66 → 63.

## Revert

```bash
cd build/core && git apply -R ../../patches/0003-floating-table-anchor/fix.patch
scripts/host/build-timed.sh build-incremental   # ~10 s
scripts/host/build-timed.sh snapshot-custom
```
