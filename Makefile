# One command per job. Run `make help` to list them.
.PHONY: help setup check test test-real web dev

help:            ## List the commands
	@grep -E '^[a-z-]+:.*##' Makefile | sed 's/:.*##/ →/'

setup:           ## Install Python and web dependencies
	pip install -r requirements.txt pytest ruff
	cd web && npm ci

check: test web  ## Everything CI runs, locally

test:            ## Python lint + tests
	ruff check --select E9,F63,F7,F82 .
	python -m pytest -q

test-real:       ## Tests with the real embedding model (slow, downloads once)
	RUN_EMBED_TESTS=1 python -m pytest -q tests/test_script_recognition.py tests/test_script_meanings.py

web:             ## Web types, lint, unit checks, build
	cd web && npm run check && npm run build

dev:             ## Run the API locally
	python backend/app.py
