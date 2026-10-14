# Pithy Common Instructions

This applies to both the Pithy project and dependents of that project.


# Agent Development Workflow

* In general, run `just check` before declaring done. When the checks pass simply say "Checks pass."
  Skip this step for changes where the actions performed by `check` are clearly irrelevant or unchanged.
* Verify file changes with `git status` and `git diff`.

## Finding and Using Context

### Agent Instructions

All projects use `craft-context` to maintain agent instructions.
`CTX.md` and its imported files are the instruction sources.
Each `CTX.md` produces a sibling `AGENTS.md` containing the expanded instructions and a sibling `CLAUDE.md` symlink to `CTX.md`.
`AGENTS.md` and `CLAUDE.md` are gitignored build products; only `CTX.md` and the files it imports are committed.
`CTX.md` files can appear in subdirectories. Check for applicable local instructions when working in a subtree.

### Local Dependency Sources

Projects expose related local directories through symlinks under `deps/`, managed by `craft-deps`.
Pithy is available at `deps/pithy` in dependent projects.
Use these paths to inspect dependency implementations, tests, documentation, and instructions.
Targets may also be documentation or data directories rather than Git checkouts.

Edits through `deps/` modify the original directory and may affect other projects using it.
Before editing a dependency, read its applicable instructions and inspect its Git state; run its checks and manage its changes in that repository.
Respect its `writable` setting in `_deps.local.json`, which defaults to false.
This is an advisory permission for consuming tools; the symlink itself does not enforce it or grant filesystem access.

Commit dependency names in `_deps.json`; keep `deps/` and the machine-local path mapping `_deps.local.json` gitignored.
Relative paths in `_deps.local.json` resolve from the project root.
Use `craft-deps [project]` to configure or repair links; it prompts for missing locations and write permissions, and does not clone repositories or install packages.
Configure the links before invoking uv if its workspace depends on them.

### Find Existing Functionality

From the working project's root, query for existing solutions using `craft-context query [keywords...]`.
This searches for keywords that modules advertise in both the current project and each immediate dependency under `deps/`.
Do this even when the task does not explicitly mention a library or dependency.

When you find candidates, assess the tradeoffs of using existing solutions and discuss any concerns.

Modules advertise keywords via the special `_context_keywords_` documentation variable.
Search for technical terms describing both the problem and possible solutions, including relevant standard library identifiers.
Example: For a file concurrency problem; `craft-context query locking concurrency mutex advisory fcntl.flock`

The words of every indexed module's name match automatically, even without metadata.
Queries match individual words without regard to case; any matching word can return a module.
Quoted phrases and separate words behave identically.

A module can also declare a free-form `_context_status_` string, such as 'experimental' or 'obsolete'.
Queries show the status in parentheses after the module path; take it into account when assessing candidates.

Read relevant returned source files before deciding whether new code is necessary.
An empty result does not establish that functionality is absent: keywords are curated and may be incomplete.
If no indexes are available or the query reports an error, report the lookup limitation; do not silently skip discovery.
The context query exists primarily to aid agents so please report failures, degradation, and bad content.

Providers build their index with `craft-context index` (included in `craft-context all`). Queries only read existing indexes.
Each project maintains its own index through build recipes or precommit hooks;
indexing one project does not trigger indexing of dependencies.

### Python Code Tools

Two tools produce compact views of Python sources: `pithy.python.summarize` and `pithy.python.deps`.
Use these to orient before reading whole files. Targets are file paths, directories or dotted module names;
dotted names resolve through the running Python environment, so run the tools from the project root.
Directory and package walks omit `.ut.py` files unless `-include-utests` is given.
Summaries prefer `.pyi` interfaces over paired `.py` implementations; headers and `-locs` identify the actual source file.
Explicit file targets select that file. Dependency analysis continues to use implementations by default.

`python3 -m pithy.python.summarize TARGETS` shows the module docstring and declarations with line numbers, including decorators and docstrings.
* Append `:name,Class.method` to a target to select definitions; selectors accept glob patterns, and selecting a class lists its members.
* Without a selection each class shows a `members:` count line instead; `-members` lists them.
* The unicode ellipsis is used to indicate that content was elided.
* `-docs`: `none` omits docstrings; `first` shows the first text block; `full` shows the whole docstring.
  `default` shows the module docstring in full and the first block of all others.
* `-full` prints the complete source of the selection.
* `-locs` prefixes each line with `path:line:` so that grep output stays locatable.
* `-uses` appends the modules and symbols each definition references.

`python3 -m pithy.python.deps [TARGETS]` summarizes imports.
* `-dependencies MODULE[.symbol]` lists what a module or definition references; methods are named `Class.method`.
* `-dependents MODULE[.symbol]` lists the modules that reference it, and for a symbol prints each reference site as `path:line: source`.
* Without targets, a query searches the top-level package of the queried module; name test trees, other packages or dependent projects as targets to include them.
* Treat an empty dependents result as a lead rather than proof, and confirm with a text search.
  * Only the targets are searched, so uses in other packages, test trees or dependent projects are invisible unless named.
  * Only direct, statically resolvable references are found; see the limitations below.

For both tools, analysis is static: names in string annotations, access through `self` or other instances, and dynamic access via `getattr` or `importlib` are not resolved.
Attribute chains into packages outside the targets stop one attribute past the import.


## Code Documentation

Project documentation generally falls into these six categories:

* Readme files (`readme.md`).
* Agent instructions (`CTX.md`).
* Module docstrings.
* `pithy.cmdparse.Cmd` docstrings and associated parameter help strings.
* Definition docstrings (`class` and `def`).
* Comments.

Keep detailed documentation in one authoritative location; use brief summaries and links elsewhere to maintain discoverability.
Push details down into the lower docs layers when practical so that they live closer to the code, keeping the higher level docs concise.

Document behavior, invariants, constraints, illuminating usage examples and design rationale.
Do not maintain prose inventories of definitions, signatures, imports or callers that the code-reading tools can regenerate.

Open docstrings with a summary block of one or a few lines, then a blank line before further detail;
by default `pithy.python.summarize` shows only that first block for definitions.

After writing docs, reread them and consider whether they meet our criteria.

### Readmes

`readme.md` files are primarily for human readers, but agents should also read them.
They are often the first text read when orienting in a new project, and are presented in directory views by GitHub.
Each top-level package must have a readme.md in its containing project directory.
Further subdirectory readmes are optional and should be added only by human devs, but agents must help maintain them.
There is no strict length limit, but after a page or two consider moving detail sections into separate documents.

### Agent Instructions

`CTX.md` files are automatically presented to agents when they interact with a directory and thus serve as natural entry points.
They can import `readme.md` files with `@` syntax to share introductory material and add extra instructions for agents.

### Module Docstrings

Module docstrings are by default presented in full by `pithy.python.summarize`.
Use them for orientation, module-wide behavior and invariants.
Put details about individual definitions in their own docstrings.

### pithy.cmdparse.Cmd Docstrings and Parameter Help

The docstring of a `Cmd` subclass provides the command description in CLI help.
Write it for command users, and put argument-specific explanations in the field specifiers' `doc` strings.
In modules with commands, the module docstring can offer a summary but should not repeat the bulk of the help text.
`Cmd` also offers `help_addenda` and `epilog` to facilitate factoring out common help text.

### Definition Docstrings

These get surfaced progressively by `pithy.python.summarize` so they are the most appropriate place for knowledge about class/function behavior.
High level explanations of internals are acceptable, but prefer to push internal implementation details into comments.

### Comments

For the most part, code comments should be used to explain non-obvious aspects and rationale, not to merely narrate the following line.
The exception is for long blocks of code where comments can helpfully group related lines.

When a comment reads as summarizing a line or more of code it should be presented first.
When it reads better as a detailed explanation of some aspect, it should be presented afterwards, either on the same line or on a trailing line using this idiom:
```
something_long_and_inscrutable()
#^ The reason why.
```


## Maintaining Context

### Instruction Files

The following rules apply when editing context instruction files.

* Edit `CTX.md` or its imported sources. Do not edit generated `AGENTS.md` files or replace `CLAUDE.md` symlinks.
* Put instructions shared by Pithy and its dependent projects in Pithy's `context/common.md` or the shared files it imports.

Imports use `@./path.md` syntax. Relative paths resolve from the importing file's directory.
When using `@path` imports, never reference generated `AGENTS.md` files: their retained import paths can resolve relative to the wrong directory, so `craft-context` rejects them.
Do not reference `CLAUDE.md` symlinks either; prefer `CTX.md` instead.
Imports expand recursively, with a maximum of four hops; repeated files are included only once.

Write imports as standalone tokens, preferably on their own lines, without backticks or trailing punctuation.
Enclose literal uses of `@`, including email addresses and import examples, in code spans or fenced code blocks.
Use fenced code blocks in context instruction files; `craft-context` rejects indented code blocks to avoid ambiguous import parsing.
Close all code spans and fences.

After changing instruction sources, run `craft-context instructions` from the project root to regenerate the instructions.
`craft-context all` also refreshes the project's keyword index.
`craft-context validate` checks Python sources and keyword metadata; it does not validate instruction Markdown.

### Module Discovery Metadata

Docstrings and context metadata must be literal syntax; our tools parse them statically and without importing.
Context metadata belongs at module level. For native modules, keep public docs and metadata in `.pyi` interfaces.
`craft-context` queries prefer `.pyi` over paired `.py`; see `craft-context validate -help` for paired documentation warnings.

Include the following in `_context_keywords_`:
* well-known technical terms, including both problem and solution terms;
* significant standard library identifiers for which the module either offers a replacement or a higher-level alternative.

Keywords can be single words or short phrases of up to three words.
Module names match automatically, so keywords need not repeat them.
Keyword lists must contain unique, nonempty strings in Python's sorted order. A status must be a nonblank single-line string.
Run `craft-context validate` to check source metadata without generating files; Pithy's `just check` includes this validation.
`context/index.json` and `context/index.lock` are build products and should be gitignored.

### Shared Skills

When adding or maintaining shared project skills, put them in `context/skills`.
`.agents/skills` and `.claude/skills` are symlinks to that directory.
Keep the directory and both links committed so fresh checkouts do not require sandboxed agents to create them.

## Git State

Note the presence of staged changes, unstaged changes and untracked files before making edits.
Operators should commit or at least stage prior changes before asking you to work,
so if unreleated changes are lying around it is often an oversight worth mentioning.

## Git Commits

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

## Package Management and Dependencies

We try to keep our total dependency count low to reduce our supply chain risks.
We depend on some node tooling.
*DO NOT* use or recommend `uvx` or `npx`. Those are irresponsible because they dynamically install latest versions on invocation.
For many stable dev tools global installation is a viable option.


# Pithy Contents

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


## Pithy Project Layout

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


@./style.md
