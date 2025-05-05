# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# $@: The file name of the target of the rule.
# $<: The name of the first prerequisite.
# $^: The names of all the prerequisites, with spaces between them.
# $*: The matching string in a `%` pattern rule.

.SECONDARY: # Disable deletion of intermediate products.
.SUFFIXES: # Disable implicit rules.

# Legs perf tests.


.PHONY: _default clean help perf-%

_default: help

clean: # Clean build dir.
	rm -rf _build/*

help: # Summarize the targets of this makefile.
	@GREP_COLOR="1;32" egrep --color=always '^[a-zA-Z][^ :]+:' makefile | sort
	@echo "\nGrammars: ascii, legs, unicode"
	@echo "\nLanguages: swift, py-re, py-table"

perf-%: _build/% # <grammar>-<lang>
	time-runs 8 $^ ../../unicode-data/11_00/UnicodeData.txt

_build/%-py-table: _build/%.table.py ../../legs/__init__.py main.py
	echo '#!/usr/bin/env python3' > $@
	cat _build/$*.py main.py >> $@
	chmod +x $@

_build/%-py-re: _build/%.re.py ../../legs/__init__.py main.py
	echo '#!/usr/bin/env python3' > $@
	cat _build/$*.re.py main.py >> $@
	chmod +x $@

_build/%-swift: _build/%.swift ../../legs/legs_base.swift main.swift
	time swiftc -num-threads 8 -O $^ -o $@

_build/%.re.py: ../../grammars/%.legs ../../legs/*.py ../../legs/bin/*.py
	mkdir -p _build
	legs $< -langs python python-re swift -output $@

_build/%.table.py: ../../grammars/%.legs ../../legs/*.py ../../legs/bin/*.py
	mkdir -p _build
	legs $< -langs python python-re swift -output $@

_build/%.swift: ../../grammars/%.legs ../../legs/*.py ../../legs/bin/*.py
	mkdir -p _build
	legs $< -langs python python-re swift -output $@
