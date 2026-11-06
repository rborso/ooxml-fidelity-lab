# Family 0006 — Table cell text is segmented differently

**Status:** explained (measurement-classified, not content loss)
**Family key:** table cells with wrapped/split spans × same characters, different word boundaries
**Tier:** `SEGMENT`
**Fix class:** `renderer` (low priority) — appearance is a separate, unmeasured issue
**Affected:** `bz31914-styled-tables` (derived from `bz31914-40567`)
**Documents:** bz31914-styled-tables
**Pinned inputs:** Word `16.0.19127.20860` · `collabora/code@sha256:808410e7…` (26.04.5.2)

---

## Observed

Splitting `bz31914-40567` produced a document containing only its seven tables. Compared
with Word:

```
missing 19 ('250', '500', '360', '3000', 'Liabilities', 'Accounts')
extra   39 ('50', '0', '36', '3', '5', '9', 'Liabilitie', 's', 'Account')
```

Every "missing" token is a fragment the candidate split into pieces. Removing all spaces
from both documents gives **identical character multisets** — nothing was lost, only
segmented.

## Mechanism

**Confirmed.** The table columns are narrower in the candidate, so cell text wraps at
different points; a wrapped word becomes two text spans, and a wrapped number becomes two
tokens. `Liabilities` → `Liabilitie` + `s`, `250` → `50` + `2`.

This is a **column-width difference**, which is why the borders and fills also looked
wrong: the whole table geometry is derived from the same widths, and the styling resolves
through `tblLook` and theme colours.

## What this family does *not* cover

The visible **border colour and weight** difference is real but **not measured**. The
comparator extracts words and fonts only; there is no drawing or fill extraction, so T0-T2
are blind to it. That needs a drawing tier before anyone can claim a fix worked.

Do not fold the appearance issue into this record. It has a different mechanism —
conditional table formatting (`w:tblLook` `0620`/`0660` selecting `w:tblStylePr` blocks,
resolved through 23 `w:themeColor` references) — and a different code path.

## Evidence

```
run-20261106T063236Z  bz31914-styled-tables  SEGMENT 0.70  same_characters=True
```

## Reproduce

```bash
.venv/bin/python -m harness.cli extract \
  --doc private/corpus/bugzilla/bug31914-ReferenceDocument.docx \
  --out private/corpus/derived/bz31914-styled-tables.docx --contains tblLook

.venv/bin/python -m harness.cli run --oracle windows \
  --corpus private/corpus/manifest.yaml --only bz31914-styled-tables
```

## History

| Run | Renderer digest | Oracle build | Result |
|---|---|---|---|
| run-20261106T063236Z | `sha256:808410e7…` (26.04.5.2) | 16.0.19127.20860 | open — SEGMENT |
