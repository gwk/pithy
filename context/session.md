# Pithy

## Python Environment
* Routine recipes use `python3` and tools from the caller's `PATH`. They must not silently select or synchronize a project venv.
* At session start, inspect `command -v python3` and `python3 -c 'import sys; print(sys.executable); print(sys.prefix != sys.base_prefix)'`. Check `VIRTUAL_ENV` as supporting information, not as the authority.
* Verify that project imports resolve to this checkout, for example `python3 -c 'import pithy; print(pithy.__file__)'`. A global editable installation is valid; the absence of an active venv is not a problem.
* Preserve the user's selected environment. Do not create a `.venv`, switch interpreters, or install globally merely because a check fails. Diagnose missing dependencies and import paths first.
* Explicit setup is `just develop-global` for global editable packages and development tools, or `just develop-venv` followed by its printed activation command for a workspace venv.
* Agent tool calls may use separate shells. When using a venv, activate it in each command or consistently supply its `bin` directory on `PATH`. For a prepared uv workspace environment, wrapping the whole operation with `uv run --no-sync just check` is also supported.

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
* Format Rust sources: `just fmt-rust`; `just lint` includes clippy via `just lint-rust`.
* Generate code: `just gen`

## Build System
* `just` is used for high-level development commands.
* `make` is used for build steps that have build product dependencies.
* Run `just` and `make help` to list available commands.


@./common.md
