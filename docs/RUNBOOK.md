# Runbook — running this yourself

Everything here is operator-invoked. There is no CI.

## 1. Prerequisites

| Thing | Why |
|---|---|
| Linux host with `podman` | renderers run in pinned containers |
| Python 3.12 | the harness |
| A Windows VM with Word | the reference; see `SETUP.md` |
| `poppler-utils` | extractor cross-check |
| `ntfs-3g`, `qemu-nbd` | staging into the offline VM |
| ~200 GB disk | PDFs, page images, run records |

## 2. Bootstrap

```bash
./scripts/host/bootstrap.sh          # venv, dependencies, private tree
cp config/oracle.example.yaml    private/config/oracle.yaml
cp config/renderers.example.yaml private/config/renderers.yaml
```

## 3. First checks, in order

```bash
make test            # the harness itself
make gate            # every synthetic construct renders twice, identically
make site            # build the report site
```

Do not proceed if `make gate` fails: every number downstream depends on the renderer being
deterministic.

## 4. Building a corpus

```bash
.venv/bin/python -m harness.cli fetch --limit 40 --out private/corpus/bugzilla
cp private/corpus/bugzilla/manifest-fragment.yaml private/corpus/manifest.yaml
.venv/bin/python -m harness.cli check --manifest private/corpus/manifest.yaml --strict
```

Tracker attachments are the cheapest good corpus: already minimised, already labelled.

## 5. Measuring

```bash
make run-oracle                                             # whole corpus
.venv/bin/python -m harness.cli run --oracle windows \
  --corpus private/corpus/manifest.yaml --limit 20          # bounded
.venv/bin/python -m harness.cli run --oracle windows \
  --corpus private/corpus/manifest.yaml --only bz31914-40567
```

`--split dev|holdout` restricts to one half. Published numbers should come from `holdout`.

## 6. Reading the results

```bash
.venv/bin/python -m harness.cli cluster --run private/runs/run-XXXX
.venv/bin/python -m harness.cli drift  --run-a <older> --run-b <newer>
.venv/bin/python -m harness.cli archive --run private/runs/run-XXXX
.venv/bin/python -m harness.cli crosscheck --run private/runs/run-XXXX
```

Tiers: `T0` content lost · `FIELD` declared, accepted divergence · `FLOW` paginated
differently · `ORDER` same page, different sequence · `T1` line breaks · `T2` geometry ·
`T2-fonts` unexpected substitution · `PASS`.

## 7. Serving the site

```bash
make site
SITE_BIND=0.0.0.0 make serve
```

On the lab host this runs as `ooxml-lab-site.service`, firewalled to the internal subnets.

## 8. Troubleshooting

| Symptom | Cause |
|---|---|
| `ORACLE-FAIL`, no log line | the job never reached the VM — check staging preserves the extension |
| everything `T0` | the reference PDF has no extractable text — run `archive` |
| `make gate` fails | renderer non-determinism; nothing downstream is meaningful |
| site shows stale data | the rebuild triggers on request; hit the page again |
| `OnlyOffice ... ONLYOFFICE_URL` | no Document Server configured; see `render.py` |

## 9. What not to do

- Do not tune the comparator against the holdout split.
- Do not publish a score without the corpus version and oracle build.
- Do not assume Word is right; some findings are `adjudicate`.
