#!/usr/bin/env bash

set -e

for package in "$@"; do
  echo
  echo '--------------------------------'
  echo "package: $package"
  mkdir -p _build/dist
  set -x
  python3 setup/$package/setup.py build --build-base=_build
  python3 setup/$package/setup.py sdist --dist-dir=_build/dist
  python3 setup/$package/setup.py bdist --dist-dir=_build/dist --bdist-base=_build  --skip-build
  rm -rf $package*.egg-info
  set +x
done
