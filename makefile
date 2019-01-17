# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# $@: The file name of the target of the rule.
# $<: The name of the first prerequisite.
# $^: The names of all the prerequisites, with spaces between them.
# $*: The stem with which a pattern rule matches.

.SUFFIXES: # Disable implicit rules.

.PHONY: _default _phony clean cov docs pip-develop pip-uninstall pypi-dist pypi-upload test test-diff test-diff-pairs typecheck

# First target of a makefile is the default.
_default: test typecheck

_phony:

clean:
	rm -rf _build/*

cov:
	iotest -fail-fast -coverage

docs:
	craft-docs
	test-meta/meta-coverage.sh

install-vscode:
	craft-vscode-ext -name craft -src vscode-craft
	craft-vscode-ext -name writeup -src vscode-writeup

pip-develop:
	pip3 install -e .

pip-uninstall:
	pip3 uninstall --yes pithy

# Note: upload to pypi test server with: `$ python3 setup.py sdist upload -r pypitest`
pypi-dist:
	python3 setup.py sdist

pypi-upload:
	python3 setup.py sdist upload

test:
	iotest -fail-fast

test/%: _phony
	iotest -fail-fast $@

typecheck:
	craft-py-check iotest pithy utest.py

test-diff:
	test-diff/test.py

test-diff-data:
	rm -rf _build/test-diff/*
	test-diff/collect-diff-examples.py ../pithy ../quilt
