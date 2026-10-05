# Legs benchmarks

Use the Python environment for this checkout. The recipes use the caller's `PATH`; they do not activate or synchronize a venv.

# Compilation

From the repository root, run:

```sh
just perf-legs-compile
just perf-legs-compile legs_/langs/unicode/unicode.legs -runs 3
```

The default is `legs_/langs/legs/legs.legs`, one warmup, and three measured runs.
The report includes the interpreter, imported Legs path, platform, per-stage median/minimum/maximum times, and automaton sizes.
It rejects a Legs import from another checkout, so a global editable installation cannot silently benchmark the wrong code.

The recipe forwards grammar paths and options to `compile.py`, including multiple grammars and a warmup count:

```sh
just perf-legs-compile legs_/langs/ascii/ascii.legs legs_/langs/legs/legs.legs legs_/langs/unicode/unicode.legs -runs 5 -warmups 1
```

Each run rebuilds all modes. Parsing, NFA construction and validation, DFA construction, and minimization are timed separately.
The total is the sum of those stages; file reading, imports, reporting, and source code generation are excluded.
Minimization includes ambiguity resolution.
Cyclic garbage collection remains enabled; a collection before each run is excluded from the timings.

Compare changes on the same machine and interpreter, with the same grammar, hash seed, and run counts.
Keep other workloads idle and compare several runs; small timing differences may be noise.
The just recipe sets `PYTHONHASHSEED=0` for repeatability.

# Generated lexer runtime

```sh
make -C legs_/perf perf-ascii-py-table
make -C legs_/perf perf-unicode-py-table perf-unicode-swift
make -C legs_/perf runs=3 perf-unicode-py-table
```

Targets have the form `perf-<grammar>-<language>`.
The supplied grammars are `ascii` and `unicode`; languages are `py-table` and `swift`.
The default is eight timed runs.
These use `time-runs` to measure generated lexers reading input and counting tokens, including process startup.
The input is the repository's tracked text concatenated into `_build/repo-text.txt`, rebuilt on each invocation.
The generated lexers and Swift executables are also under this directory's `_build/`.
The lexers are generated with `legs -if-stale`, so they are recompiled only when the grammar or the legs sources change.

`run.py` is an optional `pyperf` command wrapper; the make recipes use `time-runs` instead.

# Python source lexing

`just perf-legs-python` runs `legs_/langs/python/py_bench.py`. It loads the Python lexer from `_build/langs/python.py`, compiling the grammar if that file is stale. It compares the repository's Python files and synthetic cases with Python 3.14 `tokenize`, and benchmarks both repository and Unicode workloads.
It measures the detailed Legs stream, the stdlib-compatible adapter, and stdlib separately.
Each runtime measurement consumes the token iterator without retaining the tokens, with one warmup and three measured runs by default.
Source decoding, grammar compilation and differential checks are excluded from runtime measurements; garbage collection remains enabled.
The detailed stream includes trivia and string fragments, so its token count differs from the adapted and stdlib streams.
The Legs measurements include Python coordination and allocation, while stdlib uses its native tokenizer.
Use `-runs 0` for differential checks alone.
See [the Python lexer documentation](../langs/python/readme.md) for the compatibility contract, diagnostics and development commands.
