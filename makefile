# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# $@: The file name of the target of the rule.
# $<: The name of the first prerequisite.
# $^: The names of all the prerequisites, with spaces between them.
# $*: The matching string in a `%` pattern rule.

.SECONDARY: # Disable deletion of intermediate products.
.SUFFIXES: # Disable implicit rules.

.PHONY: _default _phony clean cov docs pip-develop pip-uninstall pypi-dist pypi-upload test test-diff test-diff-pairs typecheck

.PHONY: _default clean clean-data clean-grammars cov gen gen-data gen-grammars \
  pip-develop pip-uninstall pypi-dist pypi-upload test typecheck

# First target of a makefile is the default.
_default: test typecheck

_phony:

packages := craft iotest legs pithy utest writeup

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
	./develop.sh $(packages)

docs:
	craft-docs

gen: gen-data gen-grammars

gen-data: \
	legs/unicode/data_09_00.py \
	legs/unicode/data_10_00.py \
	legs/unicode/data_11_00.py \

gen-grammars: \
	grammars/ascii.legs \
	grammars/unicode.legs \

gen-vscode: vscode-ext/syntaxes/legs.json

help: # Summarize the targets of this makefile.
	@GREP_COLOR="1;32" egrep --color=always '^\w[^ :]+:' makefile | sort

install-vscode:
	vscode-ext/install-vscode-ext.sh
	craft-vscode-ext -name craft -src vscode-craft
	craft-vscode-ext -name writeup -src vscode-writeup

pip-uninstall:
	pip3 uninstall --yes $(packages)

test: gen
	iotest -fail-fast

test/%: _phony
	iotest -fail-fast $@

typecheck: gen
	craft-py-check iotest legs pithy utest gen-data.py gen-grammar.py legs_base.py

test-diff:
	test-diff/test.py

test-diff-data:
	rm -rf _build/test-diff/*
	test-diff/collect-diff-examples.py ../pithy ../quilt


# Targets.

grammars/legs.legs: # Override the pattern rule below.

grammars/%.legs: gen-grammar.py
	./$^ $* > $@

legs/data_%.py: gen-data.py
	./$^ data/$* > $@

vscode-ext/syntaxes/legs.json: grammars/legs.legs
	legs $< -syntax-name Legs -syntax-scope legs -syntax-exts legs -langs vscode -output $@

