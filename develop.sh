#!/usr/bin/env bash

set -e

for package in "$@"; do
  echo
  echo '--------------------------------'
  echo "package: $package"
  python3 $package/setup.py install_scripts
  rm -rf $package*.egg-info
done
