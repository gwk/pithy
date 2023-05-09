#!/usr/bin/env bash

set -e

function fail { echo "error: $@" 1>&2; exit 1; }

[[ -n "$@" ]] || fail "usage: $0 [packages ...]"

proj="$PWD"
for package in "$@"; do
  cd "$proj"
  build/gen-pyproject-toml.py "$package"
  cd "pkg/$package"
  pip install .
done
