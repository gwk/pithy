#!/usr/bin/env bash

set -e

repo=$(dirname "$0")

for package in "$@"; do
  "$repo/setup.sh" "$package"
  python3 setup.py develop -v
done
rm setup.cfg
