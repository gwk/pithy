#!/usr/bin/env bash
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

set -euo pipefail

function fail { echo "error: $@" 1>&2; exit 1; }

(( $# )) || fail "usage: $0 [pip-flags ...] [packages ...]"

cd "$(dirname "$0")/.."

flags=(--no-sources)
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
# Use `just develop-global` or `just develop-venv` for editable development setups.
# With --no-sources, an intra-repo dependency must either be listed in this same invocation or already be installed;
# otherwise uv fetches it from PyPI.
install_python=$(python3 -c 'import sys; print(sys.executable)')
uv pip install --python "$install_python" "${flags[@]}" "${pkg_dirs[@]}"
