# Pithy

## Python Environment
* Routine recipes use `python3` and tools from the caller's `PATH`. They must not silently select or synchronize a project venv.
* The environment depends on the project and the worktree:
  * If the project justfile defines `develop-global`, then the `main` branch is normally installed as a global editable package.
  * Otherwise `main` is treated like any other worktree and the expectation for agent sessions is that a venv is active.
  * If the project does not define a pyproject.toml then there is no venv to activate.
* If the environment exists but a check fails, diagnose missing dependencies and import paths first.
  Do not switch interpreters, recreate the venv or install globally to work around a failure.
* If setup itself fails, for example because the network is blocked, report the failure and stop.
* Agent tool calls may use separate shells.
  A venv that the session did not inherit from the launcher must be activated in each command, or have its `bin` directory supplied first on `PATH` consistently.
  For a prepared uv workspace environment, wrapping the whole operation with `uv run --no-sync just check` is also supported.

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
