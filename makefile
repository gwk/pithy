# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

.PHONY: clean default dist upload

default: dist

_build/egg_info:
	mkdir -p $@
	./setup.py egg_info

_build/sdist: _build/egg_info
	./setup.py sdist

clean:
	rm -rf _build/*

dist: _build/sdist	

upload: dist
	./setup.py sdist upload
