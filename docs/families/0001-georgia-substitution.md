# Family 0001 — Georgia substituted with a non-metric fallback

**Status:** fixed (image-level font addition, patch 0002) — verified on the synthetic suite
**Family key:** `w:rFonts[@w:ascii='Georgia']` × `line breaks and pagination change; no data loss`
**Tier:** T1 (line breaks) with T2 (geometry) consequences
**Fix class:** `config` — font availability, not a code defect
**Affected:** 1 synthetic case so far; expected to affect any document using Georgia
**Documents:** georgia
**Pinned inputs:** `collabora/code@sha256:808410e77b8695a35b93c7638fbba07c10cf0ba8307141b460248f18ab6e5c55`
— Collabora Office 26.04.5.2, build `42745e44`; no oracle build (not yet available)

---

## Observed

A paragraph requesting **Georgia** renders with different character advances, so the line
breaks move and the page may repaginate. Text content is unchanged — T0 passes, so this is
not data loss.

Measured against Word `16.0.19127.20860` on the `georgia` synthetic case: **T1**, median
word displacement **24.52 pt**, line 1 ends `keeps` in Word and `running` in Collabora.

## Mechanism

**Confirmed.** The Collabora Online image bundles Carlito (Calibri metric clone), Caladea
(Cambria), Liberation (Arial/Times), DejaVu and a Noto subset. It ships **no Georgia, no
Calibri, no Cambria, and no metric-compatible Georgia clone** (Gelasio).

Georgia therefore falls back to **NotoSerif-Regular** — a generic serif, not a
metric-compatible substitute. Different metrics, different line breaks.

This is the same mechanism that broke the Danish Ministry of Digitization pilot's
templates, which were styled in Georgia.

## Evidence

Rendered with `Producer: Collabora Office 26.04.5.2 (X86_64)`:

```
font: BAAAAA+Carlito-Bold       TrueType   ← default body font, metric clone present
font: DAAAAA+Carlito            TrueType
font: CAAAAA+NotoSerif-Regular  TrueType   ← Georgia requested, generic fallback used
```

Minimal reproducer: a DOCX whose body is one paragraph with
`<w:rFonts w:ascii="Georgia" w:hAnsi="Georgia"/>`.

## Reproduce

```bash
podman run --rm --user 0 -e HOME=/tmp \
  -v "$PWD/in:/in:Z" -v "$PWD/out:/out:Z" \
  --entrypoint /opt/collaboraoffice/program/soffice.bin \
  collabora/code@sha256:808410e77b8695a35b93c7638fbba07c10cf0ba8307141b460248f18ab6e5c55 \
  --headless --norestore --convert-to pdf --outdir /out /in/georgia.docx

# then list embedded fonts
python -c "import pymupdf,sys; d=pymupdf.open('out/georgia.pdf'); \
print([f[3] for f in d.get_page_fonts(0)])"
```

## Decision

Not yet decided — two options, both cheap:

1. **Add Gelasio** (metric-compatible Georgia) to the renderer image. Fixes every document
   that requests Georgia, including ones received from other organisations that we do not
   control. Preferred for a migration, because incoming documents are not ours to rewrite.
2. **Remove Georgia from our templates.** Cheaper, but only helps documents we author.

Option 1 first: the whole point is handling documents from elsewhere.

Note this is *not* an argument for installing real Microsoft fonts on the renderer — that
would test a machine nobody has. Metric-compatible clones are the correct substitute.

## Fix

**Applied as `patches/0002-gelasio-font`.** A derived image, `FROM` the pinned upstream plus
a `COPY` of Gelasio into the office font directory. No compiler involved: the image has no
shell, and LibreOffice scans its own font directory, so no `fc-cache` is needed.

```
clean   fonts: Carlito, NotoSerif-Regular     ← Georgia fell back to a generic serif
custom  fonts: Carlito, Gelasio-Regular       ← metric-compatible clone
```

## Retest

| Suite | Before | After |
|---|---|---|
| synthetic `georgia` | **T1** 0.25 | **PASS** 1.00 |
| synthetic suite mean | 0.8187 | 0.9125 |
| full corpus (42 docs) | — | 0 improved, **0 degraded**, 42 unchanged |

The corpus result is the important one: adding the font changed nothing else. No corpus
document currently requests Georgia, which is why the improvement only shows on the
synthetic suite — and why the family stays open until a real document exercises it.

## History

| Run | Renderer digest | Oracle build | Result |
|---|---|---|---|
| smoke-001 | `sha256:808410e7…` (26.04.5.2) | none — no oracle yet | open |
| run-20261105T161944Z | `sha256:808410e7…` (26.04.5.2) | 16.0.19127.20860 | open (T1, 24.52 pt) |
| run-20261106T074656Z | `sha256:df0ec3c2…` (26.04.5.2 + Gelasio) | 16.0.19127.20860 | fixed — PASS |
