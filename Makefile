PYTHON ?= .venv/bin/python
COMPOSE = docker compose --env-file /dev/null -f compose.yaml

.PHONY: install lint format typecheck test check db-up db-down migrate test-integration

install:
	$(PYTHON) -m pip install -e '.[dev]'

lint:
	$(PYTHON) -m ruff check src scripts tests migrations

format:
	$(PYTHON) -m ruff format src scripts tests migrations

typecheck:
	$(PYTHON) -m mypy

test:
	$(PYTHON) -m pytest -q -m 'not integration'

check: lint typecheck test

db-up:
	$(COMPOSE) up -d --wait postgres

db-down:
	$(COMPOSE) down

migrate:
	$(PYTHON) -m alembic upgrade head

test-integration:
	$(PYTHON) -m pytest -q -m integration
