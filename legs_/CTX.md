@readme.md

@grammar.md

# Invariants

Every target and every optimization must preserve these properties of a generated lexer:
* The lexer cannot fail. Errors are emitted as `invalid` and `incomplete` tokens.
* The tokens tile the input range in order, with no gaps, overlaps or empty tokens. The optional final `end_of_text` token is the only empty one.
* Each token is the longest match in the current mode, subject to commitment barriers.
* Overlapping patterns resolve as described in `grammar.md`. Pattern order never matters.
* All targets produce the same tokens for the same input.

`legs-test` compares the targets against the reference lexer. `legs-test -props` checks the reference lexer against the NFA.

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
* `cache.py` loads a generated Python lexer, compiling it with `legs -if-stale` only when it is stale.
* `langs/` holds the code that a supplied language needs beyond its grammar, one subpackage per language.
  `langs/python` has `py_lexer.py`, `py_preprocess.py`, `py_tokenize.py` and `py_lexer_samples.py`, which implement the Python language lexer.
  They use the generator but are not part of it. `targets/python.py` is the module that writes Python lexers.

`legs_/langs` holds the supplied languages, one directory each: the grammar, a readme, tests and benchmarks.
It is not a package and has no `__init__.py` files; importable code belongs in `legs_/legs/langs`.

# Generated Files

* `langs/ascii/ascii.legs`, `langs/unicode/unicode.legs` and `character-classes.md` are generated. Regenerate them with `make gen-grammars` from the repository root.
* `wu_/wu/lex.py` is a generated lexer that is committed to the repository. It imports the runtime from `legs`. No recipe regenerates it.

# Tests

* Unit tests for a module sit beside it in `legs_/legs`. `just check` runs these.
* `just check` does not run the tests in `legs_/test`. After changing the parser, the automata or a target, run `iotest legs_/test/0 legs_/test/2`.
  These tests need the `swift` command.
* `just test-full` also runs the tests in `legs_/test`, including the property tests. See `legs_/test/CTX.md`.
* Neither runs the tests in `legs_/langs`. Run `just test-legs-langs [names...]` manually after changing a language, the compiler or a target.

# Costs

* Every supplied grammar compiles in about a second, most of which is startup and parsing.
* Any edit to the sources of `legs`, `pithy` or `tolkien` makes the generated lexers stale, so the next build recompiles them.
* The language tests and `just perf-legs-python` load the lexers from `_build/langs` through `legs.cache.cached_lexer_class`.
  Do not call `build_lexer_class` on a supplied grammar in a test; it compiles on every run.
* Measure compilation with `just perf-legs-compile`. See `perf/readme.md`.
