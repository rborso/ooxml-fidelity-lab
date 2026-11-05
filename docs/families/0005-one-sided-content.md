# Family 0005 — One engine emits text the other does not

**Status:** explained (hypothesis, two instances)
**Family key:** content present on one side only × extra tokens in the candidate
**Tier:** T0 — but the direction matters
**Fix class:** `renderer` (possibly `adjudicate`)
**Affected:** 2 documents (`bz32363-205622`, `bz36791-46282`)
**Pinned inputs:** Word `16.0.19127.20860` · `collabora/code@sha256:808410e7…` (26.04.5.2)

---

## Observed

The candidate has **more** text than the reference:

| Document | Diff | Upstream summary |
|---|---|---|
| `bz32363-205622` | extra 93 tokens | *No way to define 2 titles for a section: full vs short* |
| `bz36791-46282` | extra 7 tokens (`le`, `2011`, `Réponse`, `souhaitée`) | *Text and images are not displayed from a docx* |

## Mechanism

**Hypothesis:** both are field-expansion differences. In `bz32363` the upstream issue is
explicitly about long versus short section titles used in headers and fields; an engine that
expands a field where Word does not will emit tokens Word never rendered. In `bz36791` the
extras are French fragments consistent with field or caption text.

Direction matters for triage: "extra in candidate" is not automatically a defect. Sometimes
the reference is the one dropping content, and the correct decision is `adjudicate`.

## Evidence

```
run-20261105T194923Z  bz32363-205622  T0  extra 93
run-20261105T194923Z  bz36791-46282   T0  extra 7
```

## Decision

Undecided between `renderer` and `adjudicate`. Resolve by rendering the same document in
Word with fields toggled to show codes (`Alt+F9` equivalent) and checking whether the extra
tokens are field results Word simply did not paint.

This is exactly the case where the harness must not assume Word is right.

## Retest

Pending the adjudication.

## History

| Run | Renderer digest | Oracle build | Result |
|---|---|---|---|
| run-20261105T194923Z | `sha256:808410e7…` (26.04.5.2) | 16.0.19127.20860 | open — needs adjudication |
