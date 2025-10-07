# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# Pithy must come first for manual installation, or else pip will download the PyPI version.
packages := 'pithy crafts iotest legs pithytools tolkien utest wu'


# List all recipes; the default.
list-recipes:
  @just --list --unsorted

list-packages:
	@echo {{packages}}

build:
	sh/build.sh {{packages}}

check: lint typecheck test

cov:
	iotest -fail-fast -coverage

cov-meta:
	test-meta/meta-coverage.sh

develop:
	sh/develop.sh {{packages}}

docs:
	craft-docs

gen:
  make gen

isort:
	isort {{packages}} test tools


install:
	sh/install.sh {{packages}}

iotest:
	iotest -fail-fast

lint:
	pyflakes {{packages}}

test: gen utest iotest

test-diff:
	test-diff/test.py

test-diff-data:
	rm -rf _build/test-diff/*
	test-diff/collect-diff-examples.py ../pithy ../quilt

typecheck: gen typecheck-py

typecheck-py:
	mypy {{packages}} test tools

typecheck-js:
	tsc

typecheck-clear-cache:
	rm -rf _build/mypy_cache

typecheck-clean: typecheck-clear-cache typecheck

uninstall:
	pip3 uninstall --yes {{packages}}

vscode-links:
	ln -fs $$PWD/vscode/* ~/.vscode/extensions

vscode-insider-links:
	ln -fs $$PWD/vscode/* ~/.vscode-insiders/extensions

utest:
	python3 -m utest {{packages}} test
