# Doctor: from "this document differs" to "this line"

A patch without a trace is a guess. Guessing is rational for the first twenty
minutes because a rebuild takes 17 seconds; it is not rational afterwards, and
two guessed patches for family 0004 both cost an afternoon and fixed nothing.

The rule: **no patch until something names the junction.**

## 1. Confirm the failure is real and localised

```bash
make run                       # all three lanes, ~1 hour
```

Read `private/runs/<run>/results.json` for the document: `tier` says what the
text comparator saw, `visual` says what the pixels saw, `t0.missing_detail`
says which page lost which tokens, and `t2.fonts_unexpected` says whether a
font substitution is involved.

A document with `tier: PASS` and `visual: visible` is a rendering difference
with no text difference - borders, fills, images.

## 2. Shrink the document before reading the code

A 40-page form has forty possible causes. Cut it down until the difference
survives on one paragraph, one table or one shape. The corpus generator
(`harness/synth.py`) will emit a minimal DOCX; hand-editing the XML inside the
zip works too. Every later step is faster on a small file.

## 3. Trace the parser

Our build is not `--enable-product`, so `SAL_INFO`/`SAL_WARN` are compiled in
and filtered at runtime. No special build needed:

```bash
SAL_LOG="+writerfilter" \
  build/instdir-clean/program/soffice --headless --norestore \
  --convert-to pdf --outdir /tmp/out /tmp/minimal.docx 2>&1 | grep -i sdt
```

Useful namespaces: `+writerfilter.oox` (parser), `+writerfilter.dmapper`
(domain mapper). If the element never appears in the trace, it was dropped in
the parser; if it appears and produces no output, it was dropped downstream.
That single distinction halves the search.

Cheap, decisive experiments before code:

- replace the suspect element with equivalent plain content - if the plain
  version renders, the element itself is the trigger
- strip one attribute at a time (a `w:dataBinding`, a `w:val`) and re-render

Both are one `unzip`, one string edit and one re-render. They cost a minute and
they eliminated two wrong hypotheses for family 0004.

## 4. Read the history

```bash
git log --oneline -20 -- sw/source/writerfilter/dmapper/
git log -S'LN_CT_SdtBlock_sdtContent' --oneline -- sw/
```

The clone is shallow by default; deepen it once:

```bash
git fetch --deepen=500 origin libreoffice-26-2
```

Any limit in this code has a commit message explaining it. That is often faster
than a trace.

## 5. Patch, then measure

```bash
make build                     # incremental, ~17 s
make run                       # all three lanes
```

A patch is judged on the whole corpus, not on the reproducer: `degraded` in the
validate output is the number that matters, and the 74 known-good controls are
there to catch a fix that breaks working documents.

## What the harness cannot tell you

It measures text, geometry and pixels. It does not measure meaning: a content
control imported as plain text keeps the words and loses the control. When a
patch's acceptance criterion is semantic, write that down in the family record
and check it by hand - the comparator will not.
