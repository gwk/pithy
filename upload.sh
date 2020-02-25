#!/usr/bin/env bash

set -e

function fail { echo "error: $@" 1>&2; exit 1; }


if [[ "$1" == "-live" ]]; then
  echo "Upload to LIVE..."
  shift
  url="https://upload.pypi.org/legacy/"
else
  echo "Upload to TEST..."
  url="https://test.pypi.org/legacy/"
fi

echo "package: $1"
dist_files=$(echo _build/dist/$1-?.?.?.tar.gz)
echo "distribution files:" $dist_files
[[ $dist_files = *' '* ]] && fail "found multiple distribution files: $dist_files"

set -x
twine upload --verbose --repository-url "$url" $dist_files
set +x

