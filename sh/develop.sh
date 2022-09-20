#!/usr/bin/env bash

set -e

function fail { echo "error: $@" 1>&2; exit 1; }

[[ -n "$@" ]] || fail "usage: $0 [packages ...]"

for package in "$@"; do
  build/gen-pyproject-toml.py "$package"
  pip install -e .
done
rm pyproject.toml
