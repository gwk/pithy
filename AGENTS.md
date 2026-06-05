# Pithy Agents Guide

This repository contains code for several python packages:
- pithy: general purpose utility library.
- crafts: miscellaneous build tools.
- iotest: a tool for writing process-based tests that specify text input and output.
- legs: a lexer generator.
- pithytools: a collection of command-line tools built on pithy.
- tolkien: a simple parse token library, factored out as a minimal dependency for other tools.
- utest: a simple unit test system.
- wu: a markdown-like document format and associated tool.

## Platform Support
This project targets Python 3.14+ on modern Unix platforms. Windows is not supported.

## Agent Development Flow
- Always run `just check` before declaring done.
- Verify file changes with `git status` and `git diff`.
- New modules should follow existing patterns in similar files.

## Build Commands
- Check everything: `just check`; runs isort, lint, typecheck, test.
- Lint: `just lint`
- Typecheck: `just typecheck`
- All tests: `just test`
- Unit tests: `just utest`
- Integration tests: `just iotest`
- Test a specific file: `iotest path/to/test` or `python -m utest path/to/test.ut.py`
- Integration tests: `just iotest` or `iotest -fail-fast [path]`
- Format imports: `just isort`
- Generate code: `just gen`

## Code Style
- Python 3.14+, strict typing with mypy.
- Do not import __future__ annotations or use strings for types; 3.14 supports deferred annotations.
- 2-space indentation (not 4-space).
- Double newlines between functions.
- Double newlines between methods, except for very compact classes where no methods have blank lines.
- Triple newlines between classes that have double-newline method separation.
- Type hints required.
- Use the modern `type` keyword wherever appropriate.
- Type declarations omit spaces after colons and inside of types, e.g `def f(x:dict[str,int]) -> None: ...`.
- Use `just isort` to normalize imports.
- Use descriptive, concise variable names.
  - `el` for elements
  - `idx` for indices when passed as an argument (not just `i`).
- No bare `# type: ignore`; always add error codes.
- Prefer single quotes for strings.
- Always ask before adding external dependencies.
- Error handling: early returns, custom exceptions where they clarify intent or need to be caught, explicit error messages.
- Line length: 128 characters max; wrap long function declarations past that length, not per parameter.
- Docstrings: single quotes for brief docs, triple single-quotes for multi-line.
- Full sentences with periods in comments and docstrings.
- Do not put non-ascii characters like em-dashes or fancy quotes in code comments or docstrings unless there is is a specific
  reason to, for example if you were describing what the character is.
- `if __name__ == '__main__': main()` should always be inlined, not two lines.
- Add the following standard license text as a comment to all files that support comments:
  `Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.`

## Build System
- `just` is used for high-level development commands.
- `make` is used for build steps that have build product dependencies.
- Run `just` and `make help` to list available commands.

## Unit Tests
- Write unit tests using our own library `utest`.
- Read the entirety of `utest/__init__.py` as context for writing tests.
- Unit tests have the compound suffix `.ut.py` and should be placed in the source tree next to the module under test.
- If there is no sensible place in the source tree they can be placed somewhere reasonable in `test/` instead.
- Individual unit tests can be executed with `python` directly; use `python -m utest [directories...]` to find and run tests.
- When tests are executed with the `utest` program, they will be run from `_build/_utest` as a simple precaution against
  working directory mistakes.

## IOTest
- `iotest` is a program for running file-based input/output tests.
- Each test is run in its own directory rooted in `_build/` plus the path stem for the test.
- The stdout and stderr are captured as `.out` and `.err`; ather file outputs are presumed to be relative to the test directory.
- The outputs are left in place so that if a test fails the user can inspect them.

## Ad-hoc Testing and Inscrutable Scripting

Agents often try to run ad-hoc bash commands using /tmp or other directories.
They can run afoul of sandboxing this way, and/or trip guards requiring manual permissions.
Instead, run expermients like this in `_build/agent_scratch/`.
**IMPORTANT**: when you write test scripts, **use the Write tool**, not bash, heredocs, or other obfuscating tricks.
It is ok to remove prior files in that scratch directory; just be aware that their might be prior junk in there.
If you want to run some code, write it to a scratch file and then run it.
**DO NOT** pipe code directly into interpreters through bash where it creates an extra hazard of escapes and expansion.

**DO NOT** write/run bash scripts that are even marginally complex to do risky things like removing files.
These kinds of actions cause safety mechanisms (e.g. harness static analysis) to trip and require manual review.
If I see a loop with `rm -f` anywhere I have to stop the run; it is a huge waste of time.
If files accidentally get produced in tree that need to be cleaned up,
then list them out and `rm` them with an explanation of what happened.
If I deny permission to run a command, do not then attempt to run some other similar command; instead ask for help.
You are more productive if you stop and ask for help to clean up a mess rather than trying to script your way forward.

**Again: use the Write tool to write scratch scripts!**


# Pithy Project Layout

Each package is wrapped in an intermediate directory with an underscore suffix to isolate pyproject.toml files:
```
pithy/ (the git/project root, not the package root)
  pithy_/ (the pithy intermediate)
    pyproject.toml
    pithy (the pithy package root)
  pithytools_/
    pyproject.toml
    pithytools/ (the pithytools package root)
  ...
```

So for example when we refer to `pithy.web.server`, it is `pithy_/pithy/web/server.py` relative to the project.
If we refer to `.web.server`, we probably mean within the pithy package, or whatever package we are discussing.
