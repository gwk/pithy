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

uv pip install "${flags[@]}" "${pkg_dirs[@]}"
