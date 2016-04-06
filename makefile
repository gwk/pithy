
.PHONY: clean test

clean:
	rm -rf _build/*

test:
	./iotest.py test
