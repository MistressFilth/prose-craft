.PHONY: init sync test unit-test features-test clean lint typecheck format format-check check release help

init:
	uv sync --all-extras

sync:
	uv sync --all-extras

unit-test:
	uv run pytest tests/unit -v

features-test:
	uv run pytest tests/features -v

test: unit-test features-test

clean:
	rm -rf .ty_cache .ruff_cache .pytest_cache src/prose_craft/__pycache__ src/prose_craft/*/__pycache__ tests/__pycache__ tests/*/__pycache__
	find . -type d -name __pycache__ -exec rm -rf {} +

lint:
	uv run ruff check src tests scripts

typecheck:
	uv run ty check src/prose_craft scripts tests

format:
	uv run ruff format src tests

format-check:
	uv run ruff format --check src tests

check: lint typecheck format-check

release:
	uv run python scripts/release.py

help:
	@echo "Targets: init sync unit-test features-test test clean lint typecheck format format-check check release help"
