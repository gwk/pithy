#!/usr/bin/env bash

set -e

repo=$(dirname "$0")

function fail { echo "error: $@" 1>&2; exit 1; }

for package in "$@"; do
  "$repo/setup.sh" "$package"

  set -x
  mkdir -p _build/dist
  rm -rf _build/dist/$package* _build/lib/$package
  python3 ./setup.py build --build-base=_build
  python3 ./setup.py sdist --dist-dir=_build/dist
  python3 ./setup.py bdist --dist-dir=_build/dist --bdist-base=_build  --skip-build
  set +x
done
rm setup.cfg
