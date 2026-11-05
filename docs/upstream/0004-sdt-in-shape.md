# DRAFT — not filed

**Component:** Writer / DOCX import
**Summary:** A structured document tag (`w:sdt`) inside a floating text box is not rendered

## Steps to reproduce

1. Open `bug31914-ReferenceDocument.docx` (family 0004).
2. Export to PDF.
3. Inspect the first page's text shape.

## Actual

8 tokens are absent from the whole document: `CME`, `Offshore`, `09`, `Accounting`,
`Training`, `Exam`.

The tracker summary states it directly: *"FILEOPEN: incorrectly formatting 2007 DOCX;
missing first page text shape content with Content Controls"*.

## Expected

The content control's text is shown, as it is in Word.

## Why it is probably a nested-construct bug

Text boxes work on the DOCX path, and content controls work at body level. This document
combines the two. The importer appears to walk shape content without descending into
`w:sdt`, or to drop the `sdt` outside the body content flow.

## Suggested minimal case

A document whose body is one `w:txbxContent` containing a single `w:sdt` wrapping one run.
That isolates the combination without a third-party document, and makes a good regression
fixture.

## Environment

- Collabora Office 26.04.5.2 (`collabora/code@sha256:808410e7…`)
- Microsoft Word 16.0.19127.20860

## Evidence

```
run-20261105T194923Z  bz31914-40567  T0  missing 8
```
