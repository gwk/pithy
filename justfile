# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# Packages are ordered by interdependencies.
pkgs := 'tolkien tomul pithy utest iotest pithytools crafts wu legs tap_backblaze'

pkg_srcs := 'tolkien_/tolkien tomul_/tomul pithy_/pithy utest_/utest iotest_/iotest pithytools_/pithytools crafts_/crafts wu_/wu legs_/legs tap_backblaze_/tap_backblaze'

pkg_tests_fast := 'pithy_/test pithytools_/test utest_/test'
pkg_tests_full :=  pkg_tests_fast + ' iotest_/test legs_/test wu_/test'

# Credentials for the tap_backblaze integration suite; the read-only key restores what the read-write key uploads.
backblaze_test_creds_ro := '../creds/backblaze/tap-backblaze-test-ro.json'
backblaze_test_creds_rwd := '../creds/backblaze/tap-backblaze-test-rwd.json'

# List all recipes; the default.
list-recipes:
  @just --list --unsorted

list-packages:
  @echo {{pkgs}}

build:
  sh/build.sh {{pkgs}}

check: check-uv-lock check-pyproject isort lint typecheck test

check-full: check-uv-lock gen check-pyproject isort lint typecheck test-full

# Check that the uv lock file is in sync with pyproject.toml.
check-uv-lock:
  uv lock --check

check-pyproject:
  uv run build/check-pyproject.py {{pkgs}}

cov:
  uv run iotest {{pkg_tests_full}} -coverage

cov-meta:
  iotest_/test-meta/meta-coverage.sh

ctx:
  craft-context .

develop-global:
  sh/develop-global.sh {{pkgs}}

develop-venv:
  sh/develop-venv.sh {{pkgs}}

docs:
  uv run craft-docs

gen:
  make gen

isort:
  uv run isort {{pkg_srcs}} ops tap_backblaze_/test-integration test-diff tools

install:
  sh/install.sh {{pkgs}}

install-git-hooks:
  git config --local core.hooksPath .githooks

iotest:
  uv run iotest {{pkg_tests_fast}}

iotest-full:
  uv run iotest {{pkg_tests_full}}

lint:
  uv run pyflakes {{pkg_srcs}} ops tap_backblaze_/test-integration test-diff tools

test: utest iotest

test-full: utest iotest-full

# Run the tap_backblaze integration suite; requires credentials, see tap_backblaze_/test-integration/readme.md.
test-backblaze:
  uv run tap_backblaze_/test-integration/test_backblaze.py {{backblaze_test_creds_ro}} {{backblaze_test_creds_rwd}}

test-diff:
  uv run test-diff/test.py

test-diff-data:
  rm -rf _build/test-diff/*
  uv run test-diff/collect-diff-examples.py ../pithy ../quilt

typecheck: typecheck-py-packages typecheck-other

typecheck-py-packages:
  uv run mypy {{pkg_srcs}}

typecheck-other:
  uv run mypy ops perf tap_backblaze_/test-integration test-diff tools

typecheck-js:
  tsc

typecheck-clear-cache:
  rm -rf _build/mypy_cache

typecheck-clean: typecheck-clear-cache typecheck

uninstall:
  pip3 uninstall --yes {{pkgs}}

# Update the uv lock file to match pyproject.toml.
update-uv-lock:
  uv lock

vscode-links:
  ln -fs $$PWD/vscode/* ~/.vscode/extensions

vscode-insider-links:
  ln -fs $$PWD/vscode/* ~/.vscode-insiders/extensions

utest:
  uv run python3 -m utest {{pkg_srcs}}
