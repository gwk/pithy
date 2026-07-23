#!/usr/bin/env bash

set -euo pipefail

function fail { echo "error: $@" 1>&2; exit 1; }

(( $# )) || fail "usage: $0 [pip-flags ...] [packages ...]"

cd "$(dirname "$0")/.."

flags=()
pkg_dirs=()
for arg in "$@"; do
  if [[ "$arg" == -* ]]; then
    flags+=("$arg")
  else
    pkg_dirs+=("./${arg}_")
  fi
done

(( ${#pkg_dirs[@]} )) || fail "no packages specified."

# The repo root is a uv workspace.
# `--no-sources` prevents intra-repo dependencies (e.g. tolkien for pithy) from being installed as editable.
# Use `uv sync` for editable dev setups instead.
# With --no-sources, an intra-repo dependency must either be listed in this same invocation or already be installed;
# otherwise uv fetches it from PyPI.
uv pip install --no-sources "${flags[@]}" "${pkg_dirs[@]}"
