# Pithy Common Instructions

The following applies to both the pithy project itself and dependents of that project.

## Agent Development Flow
* In general, run `just check` before declaring done. When the checks pass simply say "All checks pass."
  This can be omitted only for changes where the agent is sure that the actions performed by `check` are irrelevant.
* Verify file changes with `git status` and `git diff`.

# Git State

Note the presence of staged changes, unstaged changes and untracked files before making edits.
Operators should commit or at least stage prior changes before asking you to work,
so if unreleated changes are lying around it is often an oversight worth mentioning.

# Git Commits

Do not commit unless instructed to do so. Never push or pull work unless explicitly told.
If you are asked to commit and are currently on `main`, you can make a new branch at your discretion.
Committing is not "shipping"; the commits will be reviewed and possibly reworked or squashed.

When writing commit messages:
* Be concise. Do not write elaborate parentheticals.
* Do not add agent attribution lines like "Co-authored by ...".
* If the changes are scoped to a submodule or package, begin with the dotted name, like 'some.deep.submodule: ...'
* If there is only one package in the repo then you may leave the top level off, like '.deep.submodule: ...'
  * The dot prefix is a convention to be respected for single package repos!
  * Do not write '.: ' for something pertaining to the top level; use a sensible description (colon is not mandatory).
* If you are instead referring to a directory (e.g. for docs or non-python changes), use a slash, e.g. 'docs/: ...'
* The first (summary) line should end with a period.
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
* crafts: miscellaneous build tools.
* iotest: a tool for writing process-based tests that specify text input and output.
* legs: a lexer generator.
* pithytools: a collection of command-line tools built on pithy.
* tap_backblaze: Backblaze B2 integration.
* tolkien: a simple parse token library, factored out as a minimal dependency for other tools.
* utest: a simple unit test system.
* wu: a markdown-like document format and associated tool.

Packages prefixed with `tap_` are Theory & Practice vendor integrations.
Each one wraps a single external service so that application projects can depend on just the integrations they use.

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
  pithytools_/
    pyproject.toml
    pithytools/ (the pithytools package root)
  ...
```

So for example when we refer to `pithy.web.server`, it is `pithy_/pithy/web/server.py` relative to the project.
If we refer to `.web.server`, we probably mean within the pithy package, or whatever package we are discussing.

## Unit Tests
* Write unit tests using our own library `utest`.
* Read the entirety of `utest/__init__.py` as context for writing tests.
* Unit tests have the compound suffix `.ut.py` and should be placed in the source tree next to the module under test.
* If there is no sensible place in the source tree they can be placed somewhere reasonable in `test/` instead.
* Individual unit tests can be executed with `python` directly; use `python -m utest [directories...]` to find and run tests.
* When tests are executed with the `utest` program, they will be run from `_build/_utest` as a simple precaution against working directory mistakes.

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
