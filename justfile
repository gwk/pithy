# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# Packages are ordered by interdependencies.
pkgs := 'tolkien tomul pithy utest iotest pithytools crafts wu legs'

pkg_srcs := 'tolkien_/tolkien tomul_/tomul pithy_/pithy utest_/utest iotest_/iotest pithytools_/pithytools crafts_/crafts wu_/wu legs_/legs'

pkg_tests_fast := 'pithy_/test pithytools_/test utest_/test'
pkg_tests_full :=  pkg_tests_fast + ' iotest_/test legs_/test wu_/test'

# List all recipes; the default.
list-recipes:
  @just --list --unsorted

list-packages:
	@echo {{pkgs}}

build:
	sh/build.sh {{pkgs}}

check: check-pyproject isort lint typecheck test

check-full: gen check-pyproject isort lint typecheck test-full

check-pyproject:
	build/check-pyproject.py {{pkgs}}

cov:
	iotest {{pkg_tests_full}} -coverage

cov-meta:
	iotest_/test-meta/meta-coverage.sh

develop-global:
	sh/develop-global.sh {{pkgs}}

develop-venv:
	sh/develop-venv.sh {{pkgs}}

docs:
	craft-docs

gen:
  make gen

isort:
	isort {{pkg_srcs}} test-diff tools

install:
	sh/install.sh {{pkgs}}

iotest:
	iotest {{pkg_tests_fast}}

iotest-full:
  iotest {{pkg_tests_full}}


link-claude-md:
	find . -name 'AGENTS.md' -print0 | xargs -0 -I {} sh -c 'ln -sf "$(basename {})" "$(dirname {})/CLAUDE.md"'

lint:
	pyflakes {{pkg_srcs}} test-diff tools

test: utest iotest

test-full: utest iotest-full

test-diff:
	test-diff/test.py

test-diff-data:
	rm -rf _build/test-diff/*
	test-diff/collect-diff-examples.py ../pithy ../quilt

typecheck: typecheck-py-packages typecheck-other

typecheck-py-packages:
	mypy {{pkg_srcs}}

typecheck-other:
	mypy perf test-diff tools

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
