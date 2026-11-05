# Family NNNN — <short name>

**Status:** new · isolated · explained · decided · fixed · verified · closed · wontfix · invalid
**Family key:** `<construct signature>` × `<diff signature>`
**Tier:** T0 · T1 · T2 · T3
**Fix class:** config · template · integration · renderer · adjudicate · invalid
**Affected:** N documents across M document classes

---

## Observed

What the diff looks like. Concrete and measurable — a number, a page, a construct. Not
"renders badly".

## Mechanism

Why it happens. Mark confidence: **hypothesis** or **confirmed**. A hypothesis without a
minimal reproducer stays a hypothesis.

## Evidence

The artifacts that prove it: minimal repro path, synthetic case, extracted layout tree,
font list, diff excerpt.

## Reproduce

```bash
# exact command, pinned inputs
```

## Decision

What will be done and why. For `adjudicate`: state what Word does wrong and why replicating
it would make the product worse.

## Fix

What actually changed. Renderer digest or oracle build before → after.

## Retest

| Metric | Before | After |
|---|---|---|
| Family documents failing | | |
| Corpus-wide new failures | — | |
| Document-class score delta | — | |

## History

| Run | Renderer digest | Oracle build | Result |
|---|---|---|---|
| | | | open · closed · regressed |
