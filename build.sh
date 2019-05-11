#!/usr/bin/env bash

set -e

for package in "$@"; do
  echo
  echo '--------------------------------'
  echo "package: $package"
  mkdir -p _build/dist
  set -x
  PACKAGE=$package python3 ./setup.py build --build-base=_build
  PACKAGE=$package python3 ./setup.py sdist --dist-dir=_build/dist
  PACKAGE=$package python3 ./setup.py bdist --dist-dir=_build/dist --bdist-base=_build  --skip-build
  set +x
done
