#!/usr/bin/env bash

set -e

for package in "$@"; do
  echo
  echo '--------------------------------'
  echo "package: $package"
  python3 setup/$package/setup.py install
  rm -rf $package*.egg-info
done
