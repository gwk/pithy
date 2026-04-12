#!/usr/bin/env bash

set -euo pipefail

function fail { echo "error: $@" 1>&2; exit 1; }

[[ -n "$@" ]] || fail "usage: $0 [packages ...]"

cd "$(dirname $0)/.."
proj_dir="$PWD"

for package in "$@"; do
  build/gen-pyproject-toml.py "$package"
  cd "$package"
  hatch build
  cd "$proj_dir"
done
