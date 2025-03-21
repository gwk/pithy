# Commands for Pithy Codebase

## Build/Test/Lint
- Build: `make build`
- Test all: `make test`
- Test specific: `iotest test/path/to/test` or `python3 -m utest test/path/to/test.ut.py`
- Unit tests: `make utest` or `python3 -m utest [paths...]`
- Integration tests: `make iotest` or `iotest -fail-fast [path]`
- Typecheck: `make typecheck` (mypy)
- Lint: `make lint` (pyflakes)
- Format imports: `make isort`

## Code Style
- Dedicated to public domain (CC0) - add license header to all files
- Python 3.13 compatible with strict type annotations
- 2-space indentation (not 4-space)
- Type hints required on public APIs
- Follow existing import style (alphabetical groups)
- Use descriptive variable names
- Avoid bare `# type: ignore` - always add error codes
- Prefer exception handling over assertion errors
- Use pytest-style `utest` for unit tests
- Use `.ut.py` suffix for unit tests, `.iot` for integration tests
- Minimize external dependencies

Run `make help` for all available commands.
