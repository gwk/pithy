#!/usr/bin/env bash

set -e

for package in "$@"; do
  echo
  echo '--------------------------------'
  echo "package: $package"
  PACKAGE=$package pip3 install -e . -v
done
