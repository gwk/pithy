# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# Routine recipes use python3 and tools from the caller's PATH. Environment setup is explicit.

# Packages are ordered by interdependencies.
pkgs := 'pyrrhus tolkien tomul pithy utest iotest taptools crafts wu legs tap_backblaze tap_betterstack'

pkg_srcs := 'pyrrhus_/pyrrhus tolkien_/tolkien tomul_/tomul pithy_/pithy utest_/utest iotest_/iotest taptools_/taptools crafts_/crafts wu_/wu legs_/legs tap_backblaze_/tap_backblaze tap_betterstack_/tap_betterstack'

pkg_tests_fast := 'pithy_/test taptools_/test utest_/test'
pkg_tests_full :=  pkg_tests_fast + ' iotest_/test legs_/test wu_/test'

# Credentials for the tap_backblaze integration suite; the read-only key restores what the read-write key uploads.
backblaze_test_creds_ro := '../creds/backblaze/tap-backblaze-test-ro.json'
backblaze_test_creds_rwd := '../creds/backblaze/tap-backblaze-test-rwd.json'

# List all recipes; the default.
list-recipes:
  @just --list --unsorted

list-packages:
  @echo {{pkgs}}

# Build all packages.
build:
  sh/build.sh {{pkgs}}

# Read the current version directly from package source.
[positional-arguments]
version package:
  @python3 -I sh/extract-version.py "$@"

# Build and publish to test or prod; pass -republish to allow the latest published version.
[positional-arguments]
publish stage package *flags:
  sh/publish.sh "$@"

# Install and check a published release; optionally name extra modules to import.
[positional-arguments]
validate-published stage package *imports:
  python3 -I sh/validate-published.py "$@"

check: check-py-rust-exts check-uv-lock check-pyproject check-context isort lint typecheck test

check-full: check-uv-lock gen check-pyproject check-context isort lint typecheck typecheck-js test-full

# Check that the committed pyo3 wrappers are current with the `.pyi` interfaces, without rewriting them.
check-py-rust-exts:
  python3 -m crafts.bin.craft_py_rust_ext -check

# Check that the uv lock file is in sync with pyproject.toml.
check-uv-lock:
  uv lock --check

check-pyproject:
  python3 build/check-pyproject.py {{pkgs}}

# Validate context keywords without generating files.
check-context:
  python3 -m crafts.bin.craft_context validate

cov:
  iotest {{pkg_tests_full}} -coverage

cov-meta:
  iotest_/test-meta/meta-coverage.sh

# Build all project context.
ctx:
  python3 -m crafts.bin.craft_context all

develop-global:
  sh/develop-global.sh {{pkgs}}

# Regenerate the Rust glue, then rebuild and install pyrrhus into the caller-selected Python.
develop-rust: gen-py-rust-exts
  uv pip install --python "$(python3 -c 'import sys; print(sys.executable)')" --no-deps --reinstall-package pyrrhus --editable ./pyrrhus_

develop-venv:
  sh/develop-venv.sh {{pkgs}}

docs:
  python3 -m crafts.bin.craft_docs

gen: gen-py-rust-exts
  make gen

# Generation must run before rebuilding pyrrhus, using crafts from the caller-selected Python.
gen-py-rust-exts:
  python3 -m crafts.bin.craft_py_rust_ext

isort:
  python3 -m isort {{pkg_srcs}} ops sh tap_backblaze_/test-integration test-diff tools

install:
  sh/install.sh {{pkgs}}

install-git-hooks:
  git config --local core.hooksPath .githooks

iotest:
  iotest {{pkg_tests_fast}}

iotest-full:
  iotest {{pkg_tests_full}}

lint: lint-py lint-rust

lint-py:
  python3 -m pyflakes {{pkg_srcs}} ops tap_backblaze_/test-integration test-diff tools

lint-rust: fmt-rust-check
  cargo clippy --manifest-path pyrrhus_/Cargo.toml -- -D warnings

# Rust sources are formatted per `rustfmt.toml`, which matches our Python indent and page width.
fmt-rust:
  cargo fmt --manifest-path pyrrhus_/Cargo.toml

fmt-rust-check:
  cargo fmt --manifest-path pyrrhus_/Cargo.toml --check

test: utest iotest

test-full: utest iotest-full

# Run the tap_backblaze integration suite; requires credentials, see tap_backblaze_/test-integration/readme.md.
test-backblaze:
  python3 tap_backblaze_/test-integration/test_backblaze.py {{backblaze_test_creds_ro}} {{backblaze_test_creds_rwd}}

test-diff:
  python3 test-diff/test.py

test-diff-data:
  rm -rf _build/test-diff/*
  python3 test-diff/collect-diff-examples.py ../pithy ../quilt

typecheck: typecheck-py-packages typecheck-other

typecheck-py-packages:
  python3 -m mypy {{pkg_srcs}}

typecheck-other:
  python3 -m mypy ops perf tap_backblaze_/test-integration test-diff tools

typecheck-js:
  tsc

typecheck-clear-cache:
  rm -rf _build/mypy_cache

typecheck-clean: typecheck-clear-cache typecheck

uninstall:
  uv pip uninstall --python "$(python3 -c 'import sys; print(sys.executable)')" {{pkgs}}

# Update the uv lock file to match pyproject.toml.
update-uv-lock:
  uv lock

vscode-links:
  ln -fs $$PWD/vscode/* ~/.vscode/extensions

vscode-insider-links:
  ln -fs $$PWD/vscode/* ~/.vscode-insiders/extensions

utest:
  python3 -m utest {{pkg_srcs}}
