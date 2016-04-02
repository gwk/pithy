# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

.PHONY: clean default develop dist upload

# first target is the default.
default: dist

_build/sdist:
	./setup.py sdist

clean:
	rm -rf _build/*

develop: dist
	pip3 install -e .

dist: _build/sdist	

uninstall:
	pip3 uninstall --yes pithy

upload: dist
	./setup.py sdist upload
