#!/usr/bin/env bash
# Set up the package for local development and run every offline check CI runs.
#
#   ./dev.sh              tests, lint, release tooling, build check
#   ./dev.sh -k sync      any pytest arguments pass straight through
set -euo pipefail
cd "$(dirname "$0")"

uv venv -q --allow-existing
uv pip install -q -e "packages/cs-plugin[test]"
uv run --no-sync pytest packages/cs-plugin "$@"
# The release tooling, against throwaway git repos.
uv run --no-sync pytest tests -q
uvx ruff check packages/ scripts/ tests/
# What PyPI will receive: an sdist and a wheel whose metadata twine accepts.
rm -rf dist && uv build -q packages/cs-plugin -o dist && uvx -q twine check --strict dist/*
