# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


.PHONY: clean test

clean:
	rm -rf _build/*

test:
	./iotest.py test
