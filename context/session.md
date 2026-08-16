# Pithy

## Build Commands
* Check everything: `just check`; runs isort, lint, typecheck, test.
* Lint: `just lint`
* Typecheck: `just typecheck`
* All tests: `just test`
* Unit tests: `just utest`
* Integration tests: `just iotest`
* Test a specific file: `iotest path/to/test` or `python -m utest path/to/test.ut.py`
* Integration tests: `just iotest` or `iotest -fail-fast [path]`
* Format imports: `just isort`
* Generate code: `just gen`

## Build System
* `just` is used for high-level development commands.
* `make` is used for build steps that have build product dependencies.
* Run `just` and `make help` to list available commands.


@./common.md
