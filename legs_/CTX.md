@readme.md

@grammar.md

# Source Layout

A grammar passes through these modules of `legs_/legs` in order:
* `parse.py` parses the grammar file into a `Grammar`. Each pattern becomes a tree of the classes in `patterns.py`.
* `build.py` builds the automata of each mode: an NFA (`nfa.py`), then a DFA, then a minimized DFA (`dfa.py`).
  The module docstring of `build.py` describes the steps. The module docstring of `dfa.py` defines the terms node and state.
* `targets/` has one module per output language. Each writes a lexer from the minimized DFAs.

The other modules:
* `__init__.py` is the runtime that generated Python lexers import.
* `bin/` holds the `legs` and `legs-test` commands.
* `props.py` implements the property checks of `legs-test -props`.
* `py_lexer.py`, `py_tokenize.py` and `py_lexer_samples.py` implement the Python language lexer described in `grammars/python.md`.
  They use the generator but are not part of it. `targets/python.py` is the module that writes Python lexers.

# Generated Files

* `grammars/ascii.legs`, `grammars/unicode.legs` and `character-classes.md` are generated. Regenerate them with `make gen-grammars` from the repository root.
* `wu_/wu/lex.py` is a generated lexer that is committed to the repository. It imports the runtime from `legs`. No recipe regenerates it.

# Tests

* Unit tests for a module sit beside it in `legs_/legs`. `just check` runs these.
* `just check` does not run the tests in `legs_/test`. After changing the parser, the automata or a target, run `iotest legs_/test/0 legs_/test/2`.
  These tests need the `swift` command.
* `just test-full` also runs the property tests and the slow unit tests. See `legs_/test/CTX.md`.

# Costs

* `grammars/python.legs` takes far longer to compile than the other grammars.
  The slow unit tests in `test/ut` and `just perf-legs-python` compile it.
* Measure compilation with `just perf-legs-compile`. See `perf/readme.md`.
* When working on the Python lexer, generate its tables once and reuse them; `grammars/python.md` shows how.
