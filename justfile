# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# Pithy must come first for manual installation, or else pip will download the PyPI version.
pkgs := 'crafts iotest legs pithy pithytools tolkien utest wu'

pkg_srcs := 'crafts_/crafts iotest_/iotest legs_/legs pithy_/pithy pithytools_/pithytools tolkien_/tolkien utest_/utest wu_/wu'

pkg_tests := 'iotest_/test legs_/test pithy_/test pithytools_/test utest_/test wu_/test'

# List all recipes; the default.
list-recipes:
  @just --list --unsorted

list-packages:
	@echo {{pkgs}}

build:
	sh/build.sh {{pkgs}}

check: lint typecheck test

cov:
	iotest {{pkg_tests}} -coverage

cov-meta:
	iotest_/test-meta/meta-coverage.sh

develop:
	sh/develop.sh {{pkgs}}

docs:
	craft-docs

gen:
  make gen

isort:
	isort {{pkg_srcs}} tools

install:
	sh/install.sh {{pkgs}}

iotest:
	iotest {{pkg_tests}}

link-claude-md:
	find . -name 'AGENTS.md' -print0 | xargs -0 -I {} sh -c 'ln -sf "$(basename {})" "$(dirname {})/CLAUDE.md"'

lint:
	pyflakes {{pkg_srcs}} tools

test: gen utest iotest

test-diff:
	test-diff/test.py

test-diff-data:
	rm -rf _build/test-diff/*
	test-diff/collect-diff-examples.py ../pithy ../quilt

typecheck: gen typecheck-py-packages typecheck-tools

typecheck-py-packages:
	mypy {{pkg_srcs}}

typecheck-tools:
	mypy tools

typecheck-js:
	tsc

typecheck-clear-cache:
	rm -rf _build/mypy_cache

typecheck-clean: typecheck-clear-cache typecheck

uninstall:
	pip3 uninstall --yes {{pkgs}}

vscode-links:
	ln -fs $$PWD/vscode/* ~/.vscode/extensions

vscode-insider-links:
	ln -fs $$PWD/vscode/* ~/.vscode-insiders/extensions

utest:
	python3 -m utest {{pkg_srcs}}
