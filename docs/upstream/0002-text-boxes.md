# DRAFT — not filed

**Component:** Writer / file import
**Summary:** Text box content is lost when opening legacy `.doc`, and duplicated when
opening a `.docx` with a bordered text box

## Steps to reproduce

1. Open `bug34722-no_text_boxes_shown.doc` (attached to the tracker, see family 0002).
2. Export to PDF.
3. Extract the text.

## Actual

139 tokens are absent from the PDF entirely — not moved to another page, not reordered.
Examples: `Lapo`, `Nr`, `UAB`, `RABEN`, `LIETUVA`.

The mirror case is `bug36791-Carte-d-invitation1.docx`: three text boxes and two drawings,
where the PDF contains **7 tokens that Word does not render**.

## Expected

Same visible content as Word, in either direction.

## Why this looks like one bug and not two

The direction reverses between the two documents. That is not consistent with "text boxes
are unsupported" — it is consistent with text-box content being traversed inconsistently:
skipped in one path, visited twice or expanded in another.

## Environment

- Collabora Office 26.04.5.2 (`collabora/code@sha256:808410e7…`)
- Microsoft Word 16.0.19127.20860 as the reference
- Reproduced with `make run-oracle` over the current corpus

## Evidence

```
run-20261105T194923Z  bz34722-43806  T0  missing 139
run-20261105T194923Z  bz36791-46282  T0  extra 7
```
