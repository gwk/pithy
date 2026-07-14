#!/usr/bin/env bash

set -euo pipefail

function fail { echo "error: $@" 1>&2; exit 1; }

[[ -n "$@" ]] || fail "usage: $0 [packages ...]"

cd "$(dirname "$0")/.."

build/check-pyproject.py "$@"

# All workspace members are installed editable by uv sync; the dev dependency group is included by default.
uv sync --all-packages
