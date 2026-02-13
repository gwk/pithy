# Pithy Codebase Guidelines

This repository contains code for several python packages:
- pithy: general purpose utility library.
- crafts: miscellaneous build tools.
- iotest: a tool for writing process-based tests that specify text input and output.
- legs: a lexer generator.
- pithytools: a collection of command-line tools built on pithy.
- tolkien: a simple parse token library, factored out as a minimal dependency for other tools.
- utest: a simple unit test system.
- wu: a markdown-like document format and associated tool.

## Build Commands
- Check everything: `just check`; runs lint, typecheck, test.
- Lint: `just lint`
- Typecheck: `just typecheck`
- All tests: `just test`
- Unit tests: `just utest`
- Integration tests: `just iotest`
- Test a specific file: `iotest test/path/to/test` or `python -m utest test/path/to/test.ut.py`
- Integration tests: `just iotest` or `iotest -fail-fast [path]`
- Format imports: `just isort`
- Generate code: `just gen`

## Code Style
- Python 3.14+, strict typeing with mypy.
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
- Add the following standard license text as a comment to all files that support comments:
  `Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.`

## Build System
- `just` is used for high-level development commands.
- `make` is used for build steps that have dependencies that need to be managed.
- Run `just help` and `make help` to list available commands.

## Unit Tests
- Write unit tests using our in-house library `utest`.
- Read the entirety of `utest/__init__.py` as context for writing tests.
- Unit tests have the compound suffix `.ut.py` and should be placed in the source tree next to the module under test.
- If there is no sensible place in the source tree they can be placed somewhere reasonable in `test/` instead.


# Claude Code Restrictions

Claude Code will sometimes be run as the `agent` user, which should have its permissions restricted.
For example, source files will belong to `agent:agent` with permissions `660` to allow the agent to modify the code,
or `640` for read-only permissions.

IMPORTANT: if Claude encounters a permission error, IT MUST stop and notify the user. DO NOT ATTEMPT TO ALTER FILE PERMISSIONS.

When in doubt, stop and ask questions!
