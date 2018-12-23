# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# $@: The file name of the target of the rule.
# $<: The name of the first prerequisite.
# $^: The names of all the prerequisites, with spaces between them.
# $*: The stem with which an implicit rule matches.

.SECONDARY: # Disable deletion of intermediate products.
.SUFFIXES: # Disable implicit rules.

.PHONY: _default clean clean-data clean-grammars cov gen gen-data gen-grammars \
  pip-develop pip-uninstall pypi-dist pypi-upload test typecheck

# First target of a makefile is the default.
_default: test typecheck

clean:
	rm -rf _build/*

clean-data:
	rm legs/data_*.py

clean-grammars:
	rm grammars/{ascii,unicode}.legs

cov:
	iotest -fail-fast -coverage

gen: gen-data gen-grammars

gen-data: \
	legs/unicode/data_09_00.py \
	legs/unicode/data_10_00.py \
	legs/unicode/data_11_00.py \

gen-grammars: \
	grammars/ascii.legs \
	grammars/unicode.legs \

gen-vscode: vscode-ext/syntaxes/legs.json

install-vscode: gen-vscode
	vscode-ext/install-vscode-ext.sh

pip-develop:
	pip3 install -e .

pip-uninstall:
	pip3 uninstall --yes pithy

pypi-dist:
	python3 setup.py sdist

pypi-upload: pypi-dist
	python3 setup.py sdist upload

test: gen
	iotest -fail-fast

typecheck: gen
	craft-py-check legs gen-data.py gen-grammar.py legs_base.py -deps pithy


# Targets.

grammars/legs.legs: # Override the pattern rule below.

grammars/%.legs: gen-grammar.py
	./$^ $* > $@

legs/data_%.py: gen-data.py
	./$^ data/$* > $@

vscode-ext/syntaxes/legs.json: grammars/legs.legs
	legs $< -syntax-name Legs -syntax-scope legs -syntax-exts legs -langs vscode -output $@


# Perf.

.PHONY: perf-% perf-gen-%

perf-%: _build/perf/% # <grammar>-<lang>
	time-runs 8 $^ data/11_00/UnicodeData.txt

_build/perf/%-py-table: _build/perf/%.py legs_base.py perf/main.py
	echo '#!/usr/bin/env python3' > $@
	cat _build/perf/$*.py perf/main.py >> $@
	chmod +x $@

_build/perf/%-py-re: _build/perf/%.re.py legs_base.py perf/main.py
	echo '#!/usr/bin/env python3' > $@
	cat _build/perf/$*.re.py perf/main.py >> $@
	chmod +x $@

_build/perf/%-swift: _build/perf/%.swift legs/legs_base.swift perf/main.swift
	time swiftc -num-threads 8 -O $^ -o $@

_build/perf/%.re.py: grammars/%.legs legs/*.py
	mkdir -p _build/perf
	legs $< -langs python python-re swift -output $@

_build/perf/%.table.py: grammars/%.legs legs/*.py
	mkdir -p _build/perf
	legs $< -langs python python-re swift -output $@

_build/perf/%.swift: grammars/%.legs legs/*.py
	mkdir -p _build/perf
	legs $< -langs python python-re swift -output $@
