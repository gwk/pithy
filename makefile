# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# $@: The file name of the target of the rule.
# $<: The name of the first prerequisite.
# $^: The names of all the prerequisites, with spaces between them.


.PHONY: _default clean typecheck

# First target of a makefile is the default.
_default: typecheck

clean:
	rm -rf _build/*

typecheck:
	craft-py-check craft
