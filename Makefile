.PHONY: init sync test unit-test features-test clean lint typecheck format check release help

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
	rm -rf .ruff_cache .mypy_cache .pytest_cache src/prose_craft/__pycache__ src/prose_craft/*/__pycache__ tests/__pycache__ tests/*/__pycache__
	find . -type d -name __pycache__ -exec rm -rf {} +

lint:
	uv run ruff check src tests

typecheck:
	uv run mypy src/prose_craft

format:
	uv run ruff format src tests

check: lint typecheck format

release:
	uv run python -m build
	git tag v$(uv version --short)
	git push --tags

help:
	@echo "Targets: init sync unit-test features-test test clean lint typecheck format check release help"
