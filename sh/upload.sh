#!/usr/bin/env bash

set -euo pipefail

function fail { echo "error: $@" 1>&2; exit 1; }

[[ $# -ge 1 ]] || fail "usage: $0 [-live] package"

package="$1"

if [[ "$package" == "-live" ]]; then
  echo "Upload to LIVE..."
  shift
  [[ $# -ge 1 ]] || fail "usage: $0 [-live] package"
  package="$1"
  repository="pypi"
else
  echo "Upload to TEST..."
  repository="testpypi"
fi

[[ -n "$package" ]] || fail "package name is empty."

cd "$(dirname "$0")/.."

echo "package: $package"
[[ -d "${package}_" ]] || fail "package directory not found: ${package}_"
cd "${package}_"
[[ -d dist ]] || fail "dist directory not found: ${package}_/dist"

regex=".*/$package-[0-9.]*\.tar\.gz"
dist_files=$(find dist/ -regex "$regex")
[[ -n "$dist_files" ]] || fail "no distribution files found matching: $regex"

dist_count=$(echo "$dist_files" | wc -l)
[[ "$dist_count" -eq 1 ]] || fail "found multiple distribution files:
$dist_files"

echo "distribution file: $dist_files"

set -x
twine upload --verbose --repository "$repository" "$dist_files"
set +x
