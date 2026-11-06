# Operator-driven workflow.
#
# THERE IS DELIBERATELY NO CI/CD IN THIS PROJECT.
# Every run is invoked by a human from a terminal, with pinned inputs, and
# produces a recorded run. No webhooks, no workflows, no scheduled pipelines.
# If a run matters, it is reproducible from the command line and the run
# record says exactly what was used.
#
# The harness CLI is not implemented yet (pre-M0). These targets define the
# interface it must satisfy; until then most of them will fail.

PYTHON ?= .venv/bin/python
PIP    ?= .venv/bin/pip

.DEFAULT_GOAL := help

.PHONY: help venv check gate run report test clean

help:
	@grep -E '^## ' Makefile | sed 's/^## //'

## Create the Python environment and install dependencies
venv:
	python3.12 -m venv .venv
	$(PIP) install -U pip
	$(PIP) install pymupdf lxml python-docx pydantic pyyaml typer \
	               duckdb pikepdf imagehash pillow pytest markdown

## Validate the corpus manifest against its schema
check:
	$(PYTHON) -m harness.cli check --manifest private/corpus/manifest.yaml

## Oracle determinism gate (SETUP.md §10) — go/no-go before anything else
gate:
	$(PYTHON) -m harness.cli gate --workdir private/runs/gate

CORPUS ?= private/corpus/manifest.yaml
PATCH  ?= patches/0001-sdt-in-textbox
LOCK   := scripts/host/lab-lock.sh

## Render the corpus and score it (synthetic docs when --corpus is omitted)
run:
	$(LOCK) run $(PYTHON) -m harness.cli run --out private/runs

## Same, but with the real Windows oracle (boots the VM, renders offline)
run-oracle:
	$(LOCK) run-oracle $(PYTHON) -m harness.cli run --oracle windows --corpus $(CORPUS) --out private/runs

## Baseline against the clean upstream renderer
run-clean:
	$(LOCK) run-clean $(PYTHON) -m harness.cli run --oracle windows --renderer clean --corpus $(CORPUS) --out private/runs

## Same corpus against the custom renderer (needs CUSTOM_SOFFICE or CUSTOM_IMAGE)
run-custom:
	$(LOCK) run-custom $(PYTHON) -m harness.cli run --oracle windows --renderer custom --corpus $(CORPUS) --out private/runs

## Install build dependencies and report whether this machine is adequate
prepare-build:
	scripts/host/prepare-build.sh

## Apply one patch and rebuild (needs LO_SRC; takes the lab lock)
build:
	$(LOCK) build scripts/host/build-custom.sh $(PATCH)

## One patch, full cycle: build, clean run, custom run, validate
batch:
	$(LOCK) batch scripts/host/batch.sh $(PATCH)

## Re-render the report for the most recent run
report:
	@latest=$$(ls -dt private/runs/run-* 2>/dev/null | head -1); \
	[ -n "$$latest" ] || { echo "no runs yet"; exit 1; }; \
	echo "run: $$latest"; \
	$(PYTHON) -m harness.cli report --run "$$latest"

## Build the static report site into private/site
site:
	$(PYTHON) -m harness.cli site --out private/site

## Serve the report site (internal only; set SITE_BIND to expose it)
serve:
	$(PYTHON) scripts/host/serve.py --bind $${SITE_BIND:-127.0.0.1} --port $${SITE_PORT:-8080}

## Run the harness's own tests
test:
	$(PYTHON) -m pytest -q

## Remove local scratch files (never touches private/)
clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf .pytest_cache
