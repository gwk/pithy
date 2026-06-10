#!/usr/bin/env bash

set -euo pipefail

function fail { echo "error: $@" 1>&2; exit 1; }

[[ -n "$@" ]] || fail "usage: $0 [packages ...]"

cd "$(dirname "$0")/.."
proj_dir="$PWD"

for package in "$@"; do
  build/check-pyproject.py "$package"
  cd "${package}_"
  pip --disable-pip-version-check install -e .
  cd "$proj_dir"
done
