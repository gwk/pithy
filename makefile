# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# $@: The file name of the target of the rule.
# $<: The name of the first prerequisite.
# $^: The names of all the prerequisites, with spaces between them.
# $*: The matching string in a `%` pattern rule.

.SECONDARY: # Disable deletion of intermediate products.
.SUFFIXES: # Disable implicit rules.

.PHONY: clean clean-grammars clean-legs-data gen gen-data gen-grammars gen-sqlite-extracted-sql gen-vscode-legs help vscode-links vscode-insider-links

# First target of a makefile is the default.
_default: help

clean:
	rm -rf _build/*

clean-grammars:
	rm grammars/{ascii,unicode}.legs

clean-legs-data:
	rm legs/data_*.py

gen: gen-data gen-grammars

gen-data: \
	pithy/unicode/data_09_00.py \
	pithy/unicode/data_10_00.py \
	pithy/unicode/data_11_00.py \

gen-sqlite-extracted-sql:
	tools/gen-sqlite-test-sql.py -i ~/external/sqlite -o _misc/sqlite-extracted-stmts

gen-grammars: \
	grammars/ascii.legs \
	grammars/unicode.legs \

gen-vscode-legs: vscode/legs/syntaxes/legs.json

help: # Summarize the targets of this makefile.
	@GREP_COLOR="1;32" egrep --color=always '^[a-zA-Z][^ :]+:' makefile | sort

# Targets.

grammars/ascii.legs: tools/gen-charset-grammar.py
	./$^ ascii > $@

grammars/unicode.legs: tools/gen-charset-grammar.py
	./$^ unicode > $@

legs/data_%.py: tools/gen-data.py
	./$^ data/$* > $@

vscode/legs/syntaxes/legs.json: grammars/legs.legs
	legs $< -syntax-name Legs -syntax-scope legs -syntax-exts legs -langs vscode -output $@
