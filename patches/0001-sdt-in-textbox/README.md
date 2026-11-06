# 0001 — import `w:sdt` nested inside `w:txbxContent`

Fixes family **0004**. Reproducer: `bz31914-sdt-textbox`.

## The change

`writerfilter` walks shape text bodies without handling `w:sdt`, so a block-level
structured document tag inside a text box is skipped and its runs never reach the domain
mapper. The body and table-cell paths already push and pop `SdtContext`; the shape
text-body path does not.

**Cause confirmed by experiment** (family 0004): unwrapping the `sdt` restores all 8 words;
removing the VML text-box chain does not. The chain is not involved.

The patch adds `sdt` to the elements the shape text-body context handles and routes them
through the existing `SdtContext` push/pop, so the control's content is imported like any
other block content.

Scope, precisely:

- `sw/source/writerfilter/ooxml/` — the shape text-body context's accepted element table
- `sw/source/writerfilter/dmapper/SdtHelper.cxx` — only if the block-level form needs
  placeholder handling suppressed; a block `sdt` has no placeholder run
- a narrower first version can treat `sdt` there as a transparent wrapper and import
  `w:sdtContent`'s children. That restores the text but loses control semantics, so it is a
  stopgap rather than the fix

**Path note:** from 26.2 the `writerfilter` module is merged into `sw`. The dmapper lives at
`sw/source/writerfilter/dmapper/`, not the standalone `writerfilter/` tree that older
branches use. A patch written against the old path will not apply, and the regression test
belongs at `sw/qa/writerfilter/dmapper/`.

## Apply

```bash
cd <libreoffice-source>
git apply /path/to/patches/0001-sdt-in-textbox/fix.patch
```

Build with the Collabora Online makefile, then tag by digest and record it in `patch.yaml`.

## Revert

```bash
cd <libreoffice-source>
git apply -R /path/to/patches/0001-sdt-in-textbox/fix.patch
```

Rebuild and retag as the clean image. The clean build is never modified in place.

## Verify

```bash
make run-clean     # bz31914-sdt-textbox should be T0
make run-custom   # should be PASS or SEGMENT
.venv/bin/python -m harness.cli drift --run-a <clean> --run-b <custom>
```

Acceptance: the reproducer improves **and** no other document's tier drops.

## Known gaps

- This does not address the table appearance in `bz31914-styled-tables` (family 0006).
  That is a style/theme resolution problem on a different code path.
- The harness cannot see border colour or weight today, so any visual claim about the
  tables is unverifiable until a drawing tier exists.

## Status

Draft. No `fix.patch` yet — the patch requires a LibreOffice source tree and a build, which
this environment does not have. The metadata, reproducer, acceptance test and reversal are
in place so the fix can be applied and measured without redesigning anything.

## Attempts (2026-11-06)

Two variants were built and measured; neither changed the rendering. Recorded
here so they are not repeated.

1. Guard `setControlType(plainText)` at `LN_CT_SdtBlock_sdtContent` with
   `!IsInShape()`. No effect: `<w:text>` in `sdtPr` already sets `plainText`
   earlier (DomainMapper.cxx:3428), so the `unknown` branch never runs.
2. Force `SdtControlType::unsupported` whenever `IsInShape()`. No effect.

Control experiments on `bz31914-sdt-textbox` (VML `v:rect` → `v:textbox` →
`w:txbxContent`):

| variant | "CME Offshore" in PDF |
|---|---|
| original | no |
| plain paragraph inserted into the same `txbxContent` | **yes** |
| `w:dataBinding` removed from the `sdt` | no |

So the shape text body is imported correctly and the data binding is not the
cause; the `w:sdt` subtree itself disappears. It is therefore lost before the
domain mapper sees it, most likely in the VML textbox path: `ShadowContext`
records every child, and the replay runs through
`OOXMLFastContextHandlerWrapper::lcl_createFastChildContext`, where the
namespace/token sets decide whether an element goes to writerfilter or to oox.

Next step is an instrumented run of that replay path, not another guess at the
dmapper.
