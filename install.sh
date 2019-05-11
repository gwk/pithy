#!/usr/bin/env bash

set -e

for package in "$@"; do
  echo
  echo '--------------------------------'
  echo "package: $package"
  PACKAGE=$package python3 setup/setup.py install
done
