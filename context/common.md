# Pithy Common Instructions

The following applies to both the pithy project itself and dependents of that project.

## Agent Development Flow
* In general, run `just check` before declaring done. When the checks pass simply say "Checks pass."
  This can be omitted for changes where the agent is sure that the actions performed by `check` are irrelevant or unchanged.
* Verify file changes with `git status` and `git diff`.

## Find Existing Functionality Before Implementing From Scratch

From the working project's root, query for existing solutions using `craft-context query [keywords...]`.
This searches for keywords that modules advertise, for both the local project and each immediate dependency under `deps/`.
Do this even when the task does not explicitly mention a library or dependency.

When you find candidates, assess the tradeoffs of using existing solutions and discuss any concerns.

Modules advertise keywords via the special `_context_keywords_` documentation variable. These should include:
* well-known technical terms, including both problem and solution terms;
* significant standard library identifiers for which the module either offers a replacement or a higher-level alternative.

Therefore when agents make queries they should include such terms.
Example: For a file concurrency problem; `craft-context query locking concurrency mutex advisory fcntl.flock`

Keywords can be single words or short phrases of up to three words.
The words of the module name match automatically, so keywords need not repeat them.

Queries match individual words without regard to case; any matching word can return a module.
Quoted phrases and separate words behave identically.

A module can also declare a free-form `_context_status_` string, such as 'experimental' or 'obsolete'.
Queries show the status in parentheses after the module path; take it into account when assessing candidates.

Read relevant returned source files before deciding whether new code is necessary.
An empty result does not establish that functionality is absent: keywords are curated and may be incomplete.
If no indexes are available or the query reports an error, report the lookup limitation; do not silently skip discovery.
The context query exists primarily to aid agents so they must report failures and degradation.

Providers build their index with `craft-context index` (included in `craft-context all`).
Queries only read existing indexes. Each project maintains its own index through build recipes or precommit hooks; indexing does not refresh dependencies.
Keyword lists must contain unique, nonempty strings in Python's sorted order. A status must be a nonblank single-line string.
Run `craft-context validate` to check source metadata without generating files; Pithy's `just check` includes this validation.

# Git State

Note the presence of staged changes, unstaged changes and untracked files before making edits.
Operators should commit or at least stage prior changes before asking you to work,
so if unreleated changes are lying around it is often an oversight worth mentioning.

# Git Commits

Do not commit unless instructed to do so. Never push or pull work unless explicitly told.
If you are asked to commit and are currently on `main`, you can make a new branch at your discretion.
Committing is not "shipping"; the commits will be reviewed and possibly reworked or squashed.
Err on the side of separating work into smaller commits; they should represent one conceptual step forward.
It is much easier to squash commits together than split them apart, and smaller commits are more amenable to reordering.

When writing commit messages:
* Be concise. Do not write elaborate parentheticals.
* Do not add agent attribution lines like "Co-authored by ...".
* If the changes are scoped to a submodule or package, begin with the dotted name, like 'some.deep.submodule: ...'
* If there is only one package in the repo then you may leave the top level off, like '.deep.submodule: ...'
  * The dot prefix is a convention to be respected for single package repos!
  * Do not write '.: ' for something pertaining to the top level; use a sensible description (colon is not mandatory).
* If you are instead referring to a directory (e.g. for docs or non-python changes), use a slash, e.g. 'docs/: ...'
* End the first (summary) line with a period.
* As with markdown, do not insert hard wrap newlines in the commit message body; viewers can softwrap.
* Feel free to put newlines after sentences, semicolons and colons when the lines get long though.

## Platform Support
This project targets Python 3.14+ on modern Unix platforms. Windows is not supported.

## Package Management and Dependencies

We try to keep our total dependency count low to reduce our supply chain risks.
We depend on some node tooling.
*DO NOT* use or recommend `uvx` or `npx`. Those are irresponsible because they dynamically install latest versions on invocation.
For many stable dev tools global installation is a viable option.

## Pithy Contents

The pithy repository contains code for several python packages:
* pithy: general purpose utility library.
* pyrrhus: python utilities backed by rust extensions.
* crafts: miscellaneous build tools.
* iotest: a tool for writing process-based tests that specify text input and output.
* legs: a lexer generator.
* taptools: a collection of command-line tools built on pithy.
* tap_backblaze: Backblaze B2 integration.
* tap_betterstack: Better Stack Telemetry API client and dashboard definitions.
* tap_ops: service deployment to Fedora/systemd servers.
* tolkien: a simple parse token library, factored out as a minimal dependency for other tools.
* utest: a simple unit test system.
* wu: a markdown-like document format and associated tool.

Most of these packages are pure Python.
Pyrrhus is a native extension built with maturin and pyo3.
Because pyrrhus is a member of the uv workspace, a stable Rust toolchain is required to set up any package in this repository.
Rust code targets stable Rust.

The repository also contains `ops/`, a tree of shell scripts for setting up macOS developer machines and Fedora Linux servers.
It is not a python package; see `ops/readme.md`.


# Pithy Project Layout

The pithy project houses multiple Python packages. In order to prevent namespace shadowing in the current working directory,
each package is wrapped in an intermediate directory with an underscore suffix to isolate pyproject.toml files:
```
pithy/ (the git/project root, not the package root)
  pithy_/ (the pithy intermediate)
    pyproject.toml
    pithy (the pithy package root)
  taptools_/
    pyproject.toml
    taptools/ (the taptools package root)
  pyrrhus_/
    pyproject.toml
    Cargo.toml
    pyrrhus/ (the package root, containing both Python and Rust sources)
  ...
```

So for example when we refer to `pithy.web.server`, it is `pithy_/pithy/web/server.py` relative to the project.
If we refer to `.web.server`, we probably mean within the pithy package, or whatever package we are discussing.

## Rust

Rust-based packages keep their rust sources in the package directory, interleaved with the python sources,
so that each module's interface and implementation sit together.
Maturin compiles the whole crate into a single `{package}._{package}` extension.
The extension is named after its package rather than something generic like `_core`,
so that it is unambiguous in tracebacks and profiles when several such packages are installed together.

Every native module is three files:
* `M.pyi` declares the interface and is the module's stub
* `M.py` is generated and re-exports the module's functions from the extension, which makes the module importable
* `M.rs` is scaffolded when missing; its implementation bodies are then hand-written and never overwritten.

A crate builds exactly one extension module, so the extension is a single flat namespace: `craft-py-rust-ext` discovers
every `.pyi` in the package and generates the pyo3 wrappers into the one committed `{package}/_{package}.gen.rs`.
The wrappers of a merged interface `n` are exported as `n__f`,
so that interfaces cannot collide; the `.py` re-exports restore the declared names.
To change an interface, edit the `.pyi`, run `just gen-py-rust-exts`, then fill in the `.rs` implementation bodies. Existing `.rs` files receive stdout guidance instead of edits.
Never edit a `.gen.rs` manually. See `pyrrhus_/readme.md` for the layout and its ramifications.


## Unit Tests
* Write unit tests using our own library `utest`.
* Read the entirety of `utest/__init__.py` as context for writing tests.
* Unit tests have the compound suffix `.ut.py` and should be placed in the source tree next to the module under test.
* If there is no sensible place in the source tree they can be placed somewhere reasonable in `test/` instead.
* Individual unit tests can be executed with `python` directly; use `python -m utest [directories...]` to find and run tests.
* When tests are executed with the `utest` program, they will be run from `_build/_utest` as a simple precaution against working directory mistakes.
* Unit tests should not emit stdout/stderr unless they are failing. Add log suppression flags to functions if necessary.

## IOTest
* `iotest` is a program for running file-based input/output tests.
* IO tests are recognizable as one or more files with the extensions `.iot`, `.out` and `.err`.
* Each test is run in its own directory rooted in `_build/` plus the path stem for the test.
* The stdout and stderr are captured as `.out` and `.err`; ather file outputs are presumed to be relative to the test directory.
* The outputs are left in place so that if a test fails the user can inspect them.

## Command Line Parsing
* Use `pithy.cmdparse` for new command-line interfaces. Do not introduce new uses of `argparse` or `pithy.argparser`.
* When modifying an existing command-line interface, migrate it to `pithy.cmdparse` when practical and within task scope.
* Read the `pithy.cmdparse` module documentation and tests for its grammar and examples.
* Preserve the existing command-line interface during migration. If `pithy.cmdparse` cannot express required behavior, discuss extending it instead of silently changing behavior or falling back to `argparse`. Look out for:
  * `choices=`
  * option values using `nargs`
  * `FileType`
  * `action='version'`
  * potentially mutually exclusive options and custom actions


@./style.md
