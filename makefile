# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


.PHONY: clean default test

default: cov

clean:
	rm -rf _build/*

cov:
	test-meta/meta-coverage.sh

test:
	./iotest.py test
