# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# $@: The file name of the target of the rule.
# $<: The name of the first prerequisite.
# $^: The names of all the prerequisites, with spaces between them.


.PHONY: clean default develop dist upload

# First target of a makefile is the default.
_default: test

clean:
	rm -rf _build/*

cov:
	iotest -fail-fast -coverage

pip-develop:
	pip3 install -e .

pip-uninstall:
	pip3 uninstall --yes pithy

pypi-dist:
	./setup.py sdist

pypi-register:
	./setup.py sdist register

pypi-upload: pypi-dist
	./setup.py sdist upload

test:
	iotest -fail-fast
