# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# $@: The file name of the target of the rule.
# $<: The name of the first prerequisite.
# $^: The names of all the prerequisites, with spaces between them.
# $*: The matching string in a `%` pattern rule.

.SECONDARY: # Disable deletion of intermediate products.
.SUFFIXES: # Disable implicit rules.

.PHONY: _default _phony build clean clean-grammars clean-legs-data cov cov-meta develop docs gen gen-data gen-grammars \
  gen-vscode help install-vscode pip-uninstall test test-diff test-diff-data typecheck, typecheck-clear-cache, typecheck-clean

# First target of a makefile is the default.
_default: help

_phony: # Used to mark pattern rules as phony.

# Pithy must come first for manual installation, or else pip will download the PyPI version.
packages := pithy crafts iotest legs pithytools tolkien utest wu

build:
	sh/build.sh $(packages)

clean:
	rm -rf _build/*

clean-grammars:
	rm grammars/{ascii,unicode}.legs

clean-legs-data:
	rm legs/data_*.py

cov:
	iotest -fail-fast -coverage

cov-meta:
	test-meta/meta-coverage.sh

develop:
	sh/develop.sh $(packages)

docs:
	craft-docs

isort:
	isort $(packages) test tools

gen: gen-data gen-grammars

gen-data: \
	pithy/unicode/data_09_00.py \
	pithy/unicode/data_10_00.py \
	pithy/unicode/data_11_00.py \

gen-sqlite-extracted-sql:
	tools/gen-sqlite-test-sql.py -i ~/external/sqlite -o _misc/sqlite-extracted-stmts

gen-grammars: \
	grammars/ascii.legs \
	grammars/unicode.legs \

gen-vscode-legs: vscode/legs/syntaxes/legs.json

help: # Summarize the targets of this makefile.
	@GREP_COLOR="1;32" egrep --color=always '^[a-zA-Z][^ :]+:' makefile | sort

install:
	sh/install.sh $(packages)

lint:
	pyflakes $(packages)

test: gen
	iotest -fail-fast

test/%: _phony
	iotest -fail-fast $@

test-diff:
	test-diff/test.py

test-diff-data:
	rm -rf _build/test-diff/*
	test-diff/collect-diff-examples.py ../pithy ../quilt

typecheck: gen
	mypy $(packages) test tools

typecheck-clear-cache:
	rm -rf _build/mypy_cache

typecheck-clean: typecheck-clear-cache typecheck

uninstall:
	pip3 uninstall --yes $(packages)

vscode-links:
	ln -fs $$PWD/vscode/* ~/.vscode/extensions

vscode-insider-links:
	ln -fs $$PWD/vscode/* ~/.vscode-insiders/extensions


# Targets.

grammars/ascii.legs: tools/gen-charset-grammar.py
	./$^ ascii > $@

grammars/unicode.legs: tools/gen-charset-grammar.py
	./$^ unicode > $@

legs/data_%.py: tools/gen-data.py
	./$^ data/$* > $@

vscode/legs/syntaxes/legs.json: grammars/legs.legs
	legs $< -syntax-name Legs -syntax-scope legs -syntax-exts legs -langs vscode -output $@
