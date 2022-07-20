#!/usr/bin/env bash

set -e

for package in "$@"; do
  build/gen-pyproject-toml.py "$package"
  pip install -e .
done
rm pyproject.toml
