#!/usr/bin/env bash

set -euo pipefail

function fail { echo "error: $@" 1>&2; exit 1; }

[[ -n "$@" ]] || fail "usage: $0 [packages ...]"

cd "$(dirname $0)/.."

pkg_dirs=()
for package in "$@"; do
  pkg_dirs+=("./${package}_")
done

pip --disable-pip-version-check install "${pkg_dirs[@]}"
