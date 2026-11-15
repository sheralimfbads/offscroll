PYTHON ?= .venv/bin/python
PYTHON_MINOR := $(shell cat .python-version)
COMPOSE = docker compose --env-file /dev/null -f compose.yaml

.PHONY: venv check-python install lint format typecheck test check db-up db-down migrate test-integration

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
