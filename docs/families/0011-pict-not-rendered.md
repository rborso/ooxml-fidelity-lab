# Family 0011 — PICT images are not rendered at all

**Status:** decided (reported, not fixed)
**Family key:** `.pict` media × image absent from the render
**Tier:** T0
**Fix class:** adjudicate (decoder gap)
**Affected:** 1 document, `bz75208-94362`, 46 images

---

## Observed

`bz75208-_Tesis-v.1.2.1.docx`, a 170-page thesis, contains 46 `.png` and 46
`.pict` images. Collabora draws 46 images where Word draws 221; the drawn set is
the PNGs.

## Evidence

A minimal document containing a single `.pict` from that file, rendered by the
same binary:

```
pict   images=0   drawings=1
```

Nothing is drawn. The one drawing is a frame or placeholder.

Contrast with the metafiles, which were the reason this looked like a bigger
problem:

```
emf    images=0   drawings=25     ← vectorised, content present
wmf    ...                        ← same; bz75208-157040 has 2891 drawings
                                     in Collabora against 427 in Word
```

So "images 65 vs 17" and similar figures elsewhere in the corpus are **not** loss:
an EMF or WMF becomes vector paths, and the image count falls while the picture
stays. Only PICT has no handler.

## Decision

**Reported, not fixed.** Rendering PICT needs a decoder for an obsolete Apple
format that appears in one corpus document. The pre-check flags the document;
the fix is not worth a new image decoder.

Revisit if a real collection shows PICT in use — it would mean documents from
old Mac Word, which are plausible in archives.

## History

| Run | Result |
|---|---|
| run-20261107T203600Z | T0, 46 PICT images not drawn |
