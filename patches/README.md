# Patches

One fix at a time. Every patch is measured against the same corpus, on two builds,
and can be removed cleanly.

## Policy

1. **One patch, one family.** A patch that claims to fix two families is two patches.
2. **Always two builds.** `clean` is the upstream image; `patched` is upstream plus exactly
   one patch. The corpus runs against both, so a regression is visible immediately rather
   than at the next release.
3. **Artifacts are kept.** Every run directory is permanent: reference PDFs, candidate
   PDFs, layout hashes, results. Deleting a run destroys the evidence for a claim.
4. **No patch without a reproducer.** The family record must name a document that fails
   before and passes after.
5. **Every patch documents its reversal**, and the reversal is tested by rebuilding clean.

## Layout

```
patches/
  0001-sdt-in-textbox/
    patch.yaml        metadata: family, target, base, expected effect
    README.md         what it changes, how to apply, how to revert, known gaps
    fix.patch         the change, applies with `git apply`
```

## Workflow

```bash
# 1. Baseline on the clean build
make run-clean

# 2. Build the patched image (needs a LibreOffice source tree)
./scripts/host/build-patched.sh patches/0001-sdt-in-textbox
export PATCHED_IMAGE=ooxml-lab/collabora:0001-<sha>

# 3. Same corpus, patched build
make run-patched

# 4. Compare: degradations first, then improvements
.venv/bin/python -m harness.cli drift \
  --run-a private/runs/<clean> --run-b private/runs/<patched>
```

`drift` reports every document whose tier changed, in both directions. Any document that
moved *down* blocks the patch regardless of how many moved up.

## Reversing a patch

```bash
cd <libreoffice-source>
git apply -R patches/0001-sdt-in-textbox/fix.patch
# rebuild, retag as clean, re-run
```

The clean image is never patched in place. If a patch is wrong, the clean build already
exists and the patched one is discarded.

## Why the images are pinned by digest

A patched build that is referenced by a floating tag cannot be compared to anything: you
cannot say which bytes produced which score. Both images are recorded in every run.
