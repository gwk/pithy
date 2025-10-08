# Commands for Pithy Codebase

This repository contains code for several python packages:
- pithy: general purpose utility library.
- crafts: miscellaneous build tools.
- iotest: a tool for writing process-based tests that specify text input and output.
- legs: a lexer generator.
- pithytools: a collection of command-line tools built on pithy.
- tolkien: a simple parse token library, factored out as a minimal dependency for other tools.
- utest: a simple unit test system.
- wu: a markdown-like document format and associated tool.

## Build/Test/Lint
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
- Dedicated to public domain (CC0) - add license comment as first line to all python files.
- Python 3.14 compatible with strict type annotations.
- 2-space indentation (not 4-space).
- Type hints required.
- Use isort to normalize imports.
- Use descriptive variable names.
- Avoid bare `# type: ignore`; always add error codes.
- Use `.ut.py` suffix for unit tests.
- Minimize external dependencies, and discuss before adding new ones.

## Build System
- `just` is used for high-level development commands.
- `make` is used for build steps that have dependencies that need to be managed.
- Run `just help` and `make help` to list available commands.
