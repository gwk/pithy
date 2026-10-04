# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# $@: The file name of the target of the rule.
# $<: The name of the first prerequisite.
# $^: The names of all the prerequisites, with spaces between them.
# $*: The matching string in a `%` pattern rule.

.SECONDARY: # Disable deletion of intermediate products.
.SUFFIXES: # Disable implicit rules.

# Legs perf tests.


.PHONY: _default clean FORCE help _build/repo-text.txt

_default: help

clean: # Clean build dir.
	rm -rf _build/*

help: # Summarize the targets of this makefile.
	@GREP_COLOR="1;32" egrep --color=always '^[a-zA-Z][^ :]+:' makefile | sort
	@echo "\nGrammars: ascii, unicode"
	@echo "\nLanguages: swift, py-re, py-table"

legs_dir := ../legs

# The number of timed runs for each target; slower lexers get fewer runs. Override with `make runs=N perf-...`.
runs := 8
perf-%-py-re: runs := 2

# The lexer input is all of the tracked text in the repository, concatenated. It is rebuilt for every run.
perf_input := _build/repo-text.txt

perf-%: _build/% $(perf_input) # <grammar>-<lang>
	time-runs $(runs) $< $(perf_input)

$(perf_input):
	mkdir -p _build
	cd ../.. && git grep -Ilz '' | xargs -0 cat > legs_/perf/$@

_build/%-py-table: _build/%.py main.py
	echo '#!/usr/bin/env python3' > $@
	cat $^ >> $@
	chmod +x $@

_build/%-py-re: _build/%.re.py main.py
	echo '#!/usr/bin/env python3' > $@
	cat $^ >> $@
	chmod +x $@

_build/%-swift: _build/%.swift $(legs_dir)/targets/legs_base.swift main.swift
	time swiftc -num-threads 8 -O $^ -o $@

# The lexer rules always run. `legs -if-stale` compares the hash recorded in the output with the grammar and the legs sources.
# It leaves a current output untouched, so the programs that are built from it are not rebuilt.
# The `.re.py` rule must precede the `.py` rule, because both patterns match and this version of make uses the first.
_build/%.re.py: FORCE
	mkdir -p _build
	legs ../langs/$*/$*.legs -langs python-re -output $@ -if-stale

_build/%.py: FORCE
	mkdir -p _build
	legs ../langs/$*/$*.legs -langs python -output $@ -if-stale

_build/%.swift: FORCE
	mkdir -p _build
	legs ../langs/$*/$*.legs -langs swift -output $@ -if-stale

FORCE:
