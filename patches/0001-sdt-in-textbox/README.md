# 0001 — import `w:sdt` nested inside `w:txbxContent`

Fixes family **0004**. Reproducer: `bz31914-sdt-textbox`.

## The change

`writerfilter` walks shape text bodies without pushing an `SdtContext`, so a structured
document tag inside a text box is skipped and its runs never reach the domain mapper.
The body and table-cell paths already do this; the shape text-body path does not.

The patch adds `sdt` to the elements the shape text-body context handles and routes them
through the existing `SdtContext` push/pop, so the control's content is imported like any
other paragraph content.

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
make run-patched   # should be PASS or SEGMENT
.venv/bin/python -m harness.cli drift --run-a <clean> --run-b <patched>
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
