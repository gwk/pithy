#!/usr/bin/env bash
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

set -euo pipefail

function fail { echo "error: $@" 1>&2; exit 1; }

[[ -n "$@" ]] || fail "usage: $0 [packages ...]"

cd "$(dirname "$0")/.."

# Use HEAD's commit timestamp for reproducible archive timestamps.
SOURCE_DATE_EPOCH=$(git log -1 --format=%ct HEAD)
export SOURCE_DATE_EPOCH

for package in "$@"; do
  python3 build/check-pyproject.py "$package"
  uv build --package "$package" --no-sources --out-dir "${package}_/dist"
done
