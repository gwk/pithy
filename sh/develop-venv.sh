#!/usr/bin/env bash
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

set -euo pipefail

function fail { echo "error: $@" 1>&2; exit 1; }

[[ -n "$@" ]] || fail "usage: $0 [packages ...]"

# The development venv is always `.venv` in the checkout; uv would otherwise sync a different environment.
[[ -z "${UV_PROJECT_ENVIRONMENT:-}" ]] || fail 'UV_PROJECT_ENVIRONMENT is set; unset it to develop in the checkout .venv.'

cd "$(dirname "$0")/.."

python3 build/check-pyproject.py "$@"

# All workspace members are installed editable by uv sync; the dev dependency group is included by default.
uv sync --all-packages

# This script cannot activate the environment in its caller's shell.
printf '\nActivate the development environment in your shell before running just recipes:\n  source %q\n' \
  "$PWD/.venv/bin/activate"
