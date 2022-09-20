#!/usr/bin/env bash

set -e

function fail { echo "error: $@" 1>&2; exit 1; }

[[ -n "$1" ]] || fail "usage: $0 [package]"


if [[ "$1" == "-live" ]]; then
  echo "Upload to LIVE..."
  shift
  url="https://upload.pypi.org/legacy/"
else
  echo "Upload to TEST..."
  url="https://test.pypi.org/legacy/"
fi

echo "package: $1"
regex=".*/$1-[0-9.]*\.tar\.gz"
dist_files=$(find dist/ -regex "$regex")
echo "distribution files:" $dist_files
[[ $dist_files = *' '* ]] && fail "found multiple distribution files: $dist_files"

set -x
twine upload --verbose --repository-url "$url" $dist_files
set +x
