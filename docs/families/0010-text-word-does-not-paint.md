# Family 0010 — text Word does not paint, LibreOffice does

**Status:** analysed, classification decision needed
**Family key:** `w:tbl` with `w:tblpPr` × tokens present in Collabora, absent from Word's PDF
**Tier:** T0 (extra tokens)
**Fix class:** adjudicate or renderer
**Affected:** 6 documents, the same four tokens in each

---

## Observed

Six Hungarian forms fail T0 with **extra** tokens rather than missing ones:

```
hu-gov-9.13 / 9.15 / 9.16 / 9.21 (two variants)   extra 4
    családtagja, biztosítj, igen, nem
```

The words are in the document, in ordinary table cells, and Word's reference PDF
does not show them. LibreOffice does.

## Evidence

`családtagja` sits in a plain `<w:tc>` paragraph with ordinary runs:

```xml
<w:tc><w:tcPr><w:tcW w:w="3487" w:type="dxa"/></w:tcPr>
  <w:p><w:pPr>…</w:pPr>
    <w:proofErr w:type="spellStart"/>
    <w:r><w:rPr><w:b/><w:sz w:val="20"/></w:rPr><w:t>családtagja</w:t></w:r>
```

Ruled out by inspection: tracked changes (`w:ins`/`w:del` = 0), hidden text
(`w:vanish` = 0), content controls (`w:sdt` = 0), deleted runs, white text. These
documents contain `w:tblpPr`, and the cluster is the only one in the corpus with
it.

## What this is

The reverse of family 0009: there Collabora loses text Word shows; here
Collabora paints text Word does not. The most likely mechanism is that Word
clips a table positioned outside the page area, while LibreOffice draws it.

## Decision, under the project rules

The rules classify by what the user loses. Here the user **gains** content:
nothing Word shows is missing. That does not fit "breaking".

It fits **annoying**: everything is readable and placed, but the form shows
options Word hides. A form that displays extra answer options could mislead
someone filling it in, so it is not cosmetic either.

Recommended: **adjudicate**, with the reason recorded, and note the risk. Not
worth a renderer change until there is evidence that a user was misled by it —
and a change that makes Collabora clip tables could cost the content in family
0009's documents, which is the worse failure.

## Not yet done

- confirm the table's position is off-page in Word by measuring its box in the
  reference PDF
- confirm the same four tokens come from one table, not four

## History

| Run | Result |
|---|---|
| run-20261107T112104Z | 6 × T0 with extra tokens |

## The Hungarian forms also shift content out of the margin

Reported by eye on `hu-gov-9.21 … k-ntes_tev-kenys-g_folytat-sa_HU`, confirmed by
measurement on page 1:

```
Word      leftmost words: (55,304) '1.'  (55,360) '2.'  (55,439) '3.'  (56,496) '4.'
Collab    leftmost words: (3,497) '4.'   (3,597) 'Megtakarítással'  (3,611) 'Megélhetését'
```

From item 4 onward, Collabora places the text at x≈3 — the page edge — where
Word keeps it at the 55 pt margin. A 52 pt shift, and the content sits outside
the printed margin.

The document has two tables. The second is floating and 17175 twips wide:

```xml
<w:tblpPr w:leftFromText="141" w:rightFromText="141"
          w:vertAnchor="text" w:horzAnchor="margin" w:tblpY="497"/>
```

## Four experiments, all null

| change | `4.` position |
|---|---|
| none (source) | x = 3 |
| `w:tblInd w:w="-395"` → `0` | x = 3 |
| add `w:tblpX="0"` to `tblpPr` | x = 3 |
| remove `tblpPr` entirely | x = 3 |

The replacement strings were verified to match exactly (count = 1 each), so the
experiments were real. LibreOffice's placement of this table is therefore not
determined by indent, `tblpX`, or the presence of `tblpPr` — which contradicts
what the import code appears to do and makes this a genuine tracing job rather
than a property change.

Under the project rules this **is** breaking, unlike the extra tokens this family
was opened for: content outside the margin can be clipped when printed. The
family now has two symptoms and needs splitting.
