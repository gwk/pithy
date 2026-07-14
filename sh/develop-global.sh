#!/usr/bin/env bash
# Install packages editable into the global python, making their libraries and scripts available system-wide.
# Interdependent packages should be installed together so that all of them are editable;
# otherwise workspace dependencies get installed as frozen snapshots.

set -euo pipefail

function fail { echo "error: $@" 1>&2; exit 1; }

(( $# )) || fail "usage: $0 [packages ...]"

cd "$(dirname "$0")/.."

python="${GLOBAL_PYTHON:-/opt/py/bin/python3}"

build/check-pyproject.py "$@"

args=()
for pkg in "$@"; do
  args+=(--editable "./${pkg}_")
done

uv pip install --python "$python" "${args[@]}"
