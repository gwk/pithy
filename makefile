# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# $@: The file name of the target of the rule.
# $<: The name of the first prerequisite.
# $^: The names of all the prerequisites, with spaces between them.
# $*: The matching string in a `%` pattern rule.

.SECONDARY: # Disable deletion of intermediate products.
.SUFFIXES: # Disable implicit rules.

.PHONY: clean clean-grammars gen gen-grammars gen-sqlite-extracted-sql help

# First target of a makefile is the default.
_default: help

clean:
	rm -rf _build/*

clean-grammars:
	rm grammars/{ascii,unicode}.legs

gen: gen-grammars

gen-sqlite-extracted-sql:
	tools/gen-sqlite-test-sql.py -i ~/external/sqlite -o _misc/sqlite-extracted-stmts

gen-grammars: \
	grammars/ascii.legs \
	grammars/unicode.legs \

help: # Summarize the targets of this makefile.
	@GREP_COLOR="1;32" egrep --color=always '^[a-zA-Z][^ :]+:' makefile | sort

# Targets.

grammars/ascii.legs: tools/gen-charset-grammar.py
	./$^ ascii > $@

grammars/unicode.legs: tools/gen-charset-grammar.py
	./$^ unicode > $@
