PYTHON ?= .venv/bin/python
PYTHON_MINOR := $(shell cat .python-version)
SMOKE_SOURCE ?= hackernews
COMPOSE = docker compose --env-file /dev/null -f compose.yaml

.PHONY: venv check-python install lint format typecheck test check db-up db-down migrate test-integration smoke

venv:
	python$(PYTHON_MINOR) -m venv .venv

check-python:
	@$(PYTHON) -c 'import sys; from pathlib import Path; expected = Path(".python-version").read_text().strip(); actual = ".".join(map(str, sys.version_info[:2])); sys.exit(0 if actual == expected else "Use Python " + expected + "; recreate .venv with make venv")'

install: check-python
	$(PYTHON) -m pip install -e '.[dev]'

lint:
	$(PYTHON) -m ruff check src scripts tests migrations

format:
	$(PYTHON) -m ruff format src scripts tests migrations

typecheck:
	$(PYTHON) -m mypy

test:
	$(PYTHON) -m pytest -q -m 'not integration'

check: check-python lint typecheck test

db-up:
	$(COMPOSE) up -d --wait postgres

db-down:
	$(COMPOSE) down

migrate:
	$(PYTHON) -m alembic upgrade head

test-integration:
	$(PYTHON) -m pytest -q -m integration

# Manual only: calls the public API and writes to the configured database.
smoke: check-python
	$(PYTHON) -m offscroll.cli run $(SMOKE_SOURCE) --page-cap 1

.PHONY: setup collect-public site serve secrets
setup:
	$(MAKE) venv
	$(MAKE) install
	$(MAKE) db-up
	$(MAKE) migrate

collect-public:
	OFFSCROLL_SOURCES=hackernews,wikipedia $(PYTHON) -m offscroll.cli run-all

site:
	$(PYTHON) -m offscroll.cli build-digest
	$(PYTHON) -m offscroll.cli export-site

serve:
	.venv/bin/uvicorn offscroll.web:app --host 127.0.0.1 --port 8000 --no-access-log

secrets:
	$(PYTHON) scripts/scan_secrets.py
