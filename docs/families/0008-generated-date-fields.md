# Family 0008 — generated date fields differ by the calendar

**Status:** decided (adjudicated)
**Family key:** `w:fldSimple` with a date instruction × token `06` missing, `07` extra
**Tier:** T0 before adjudication, FIELD after
**Fix class:** adjudicate
**Affected:** 9 documents — every document in the corpus that contains `w:fldSimple`

---

## Observed

Nine documents fail at T0, each losing **one** token: `06`. Each also gains one:
`07`. No other document in the corpus contains `w:fldSimple`, so the construct
and the failure coincide exactly: 9 of 9.

```
dk-ministry-form-1..3
g-simple-field-1..5
synth-field-date
```

## Mechanism

**Confirmed.** The reference PDFs were captured on 2026-11-06. The run that
flagged these happened on 2026-11-07. The field is a date, LibreOffice renders
today's date, Word's cached reference shows the day it was rendered. The
reference PDFs are byte-identical between runs, so nothing about the renderer
changed — only the clock.

This is not a fidelity defect. A date field that did *not* update would be the
bug.

## Decision

Adjudicated, exactly like TOC regeneration in family 0005: the field result is
excluded from T0 rather than compared. `private/corpus/overrides.yaml`:

```yaml
g-simple-field-1:
  allow_missing: true
  allow_extra: true
  reason: "generated date field: reference captured 2026-11-06, run day differs"
```

Both directions are required: the day is missing *and* the new day is extra.

Retested: the three sampled documents now score `FIELD` (0.80) instead of `T0`
(0.00).

## What this costs

`allow_missing`/`allow_extra` make the document tolerant of **any** missing or
extra token, not just the date. A real regression in one of these nine would be
masked until it also changed page count or geometry. That is the price of
adjudication and it is the same price family 0005 pays.

The alternative — freezing the clock for both the oracle and the renderers — is
the correct long-term answer, and it is recorded as the remaining work: the
oracle is a Windows VM whose clock we control, and `libfaketime` would cover the
renderer side. Until both are frozen, date documents cannot be compared exactly.

## History

| Run | Result |
|---|---|
| run-20261107T095145Z | 9 × T0, adjudicated |
