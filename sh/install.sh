#!/usr/bin/env bash

set -e

script_dir=$(dirname "$0")

for package in "$@"; do
  "$script_dir/setup.sh" "$package"
  python3 setup.py install -v
done
rm setup.cfg
