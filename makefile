# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# $@: The file name of the target of the rule.
# $<: The name of the first prerequisite.
# $^: The names of all the prerequisites, with spaces between them.


.PHONY: _default clean cov pip-develop pip-uninstall pypi-dist pypi-register pypi-upload test typecheck

# First target of a makefile is the default.
_default: test typecheck

clean:
	rm -rf _build/*

cov:
	iotest -fail-fast -coverage

install-vscode: vscode-ext/syntaxes/legs.json
	vscode-ext/install-vscode-ext.sh

pip-develop:
	pip3 install -e .

pip-uninstall:
	pip3 uninstall --yes pithy

pypi-dist:
	python3 setup.py sdist

pypi-upload: pypi-dist
	python3 setup.py sdist upload

test:
	iotest -fail-fast

typecheck:
	mypy-plumage legs

vscode-ext/syntaxes/legs.json: legs.legs
	legs $< -syntax-name Legs -syntax-scope legs -syntax-exts legs -language vscode -output $@
