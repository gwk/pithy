# Pithy Agents Guide

This repository contains code for several python packages:
* pithy: general purpose utility library.
* crafts: miscellaneous build tools.
* iotest: a tool for writing process-based tests that specify text input and output.
* legs: a lexer generator.
* pithytools: a collection of command-line tools built on pithy.
* tolkien: a simple parse token library, factored out as a minimal dependency for other tools.
* utest: a simple unit test system.
* wu: a markdown-like document format and associated tool.

## Platform Support
This project targets Python 3.14+ on modern Unix platforms. Windows is not supported.

## Agent Development Flow
* Always run `just check` before declaring done.
* Verify file changes with `git status` and `git diff`.
* New modules should follow existing patterns in similar files.

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

## Code Style
* Python 3.14+, strict typing with mypy.
* Do not import `__future__` annotations or use strings for types; 3.14 supports deferred annotations.
* 2-space indentation (not 4-space).
* Double newlines between functions.
* Double newlines between methods, except for very compact classes where no methods have blank lines.
* Triple newlines between classes that have double-newline method separation.
* Type hints required.
* Use the modern `type` keyword wherever appropriate.
* Type declarations omit spaces after colons and inside of types, e.g `def f(x:dict[str,int]) -> None: ...`.
* Use `just isort` to normalize imports.
* Use descriptive, concise variable names.
  * `el` for elements
  * `idx` for indices when passed as an argument (not just `i`).
* No bare `# type: ignore`; always add error codes.
* Prefer single quotes for strings.
* Always ask before adding external dependencies.
* Error handling: early returns, custom exceptions where they clarify intent or need to be caught, explicit error messages.
* Line length: 128 characters; wrap long function declarations past that length, not per parameter.
* Do not wrap at shorter lengths; 128 is our page width.
* Docstrings: single quotes for brief docs, triple single-quotes for multi-line. Use markdown syntax, not rst.
* Use proper capitalization and periods in comments and docstrings.
* Do not put non-ascii characters like em-dashes, arrows or fancy quotes in code comments or docstrings
  unless there is is a specific reason, for example if you were describing a unicode character.
* `if __name__ == '__main__': main()` should always be inlined, not two lines.
* Add the following standard license text as a comment to all files that support comments:
  `Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.`

## Markdown Style
When authoring markdown:
* Use `#` only, never the underline syntax.
* Use `*`, not `-` for lists.
* For prose text:
  * Unlike source code, do not hard-wrap lines at a fixed column; you can rely on soft wrap.
  * Especially do not hard-wrap blockquote text.
  * You can however use line breaks after sentences.
* Wrap source code at 128 characters like we do everywhere else.
* Do not use excessive emphasis bold/italics. Only use the asterisk syntax for emphasis.
* Never use tab characters for code blocks.

## Build System
* `just` is used for high-level development commands.
* `make` is used for build steps that have build product dependencies.
* Run `just` and `make help` to list available commands.

## Unit Tests
* Write unit tests using our own library `utest`.
* Read the entirety of `utest/__init__.py` as context for writing tests.
* Unit tests have the compound suffix `.ut.py` and should be placed in the source tree next to the module under test.
* If there is no sensible place in the source tree they can be placed somewhere reasonable in `test/` instead.
* Individual unit tests can be executed with `python` directly; use `python -m utest [directories...]` to find and run tests.
* When tests are executed with the `utest` program, they will be run from `_build/_utest` as a simple precaution against working directory mistakes.

## IOTest
* `iotest` is a program for running file-based input/output tests.
* Each test is run in its own directory rooted in `_build/` plus the path stem for the test.
* The stdout and stderr are captured as `.out` and `.err`; ather file outputs are presumed to be relative to the test directory.
* The outputs are left in place so that if a test fails the user can inspect them.


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


# Git State and Commits

Note the presence of staged changes, unstaged changes and untracked files before making edits.
I try to commit or at least stage prior changes before asking you to make changes,
so if changes are lying around it is often an oversight on my part.

Do not commit unless explicitly instructed to do so.
If you are asked to commit and are currently on `main`, you can make a new branch at your discrection.
Note that committing is not "shipping"; the commits will be reviewed and possibly reworked or squashed.

When writing commit messages:
* Be concise. Do not write elaborate parentheticals.
* Do not add agent attribution lines like "Co-authored by ...".
* If the changes are scoped to a submodule or package, begin with the dotted name, like 'some.deep.submodule: ...'
* If there is only one package in the repo you can leave the top level off, like '.deep.submodule: ...'
* Do not write '.: ' for something pertaining to the top level; use a sensible description (colon is not mandatory).
* The first (summary) line should end with a period.
* As with markdown, do not insert hard wrap newlines in the commit message body; I rely on viewers to softwrap.
* Feel free to put newlines after sentences and even semicolons when the lines get long though.
