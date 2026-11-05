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
	               duckdb pikepdf imagehash pillow pytest

## Validate the corpus manifest against its schema
check:
	$(PYTHON) -m harness.cli check --manifest private/corpus/manifest.yaml

## Oracle determinism gate (SETUP.md §10) — go/no-go before anything else
gate:
	$(PYTHON) -m harness.cli gate --config private/config/oracle.yaml

## Run the whole corpus through the oracle and configured renderers
run:
	$(PYTHON) -m harness.cli run \
		--oracle   private/config/oracle.yaml \
		--renderers private/config/renderers.yaml

## Render a report from the most recent run
report:
	$(PYTHON) -m harness.cli report --latest --out reports/

## Run the harness's own tests
test:
	$(PYTHON) -m pytest -q

## Remove local scratch files (never touches private/)
clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf .pytest_cache
