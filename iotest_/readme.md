
# IOTest

iotest is a small tool for testing command line programs. By default it writes the stdout and stderr of the program under test to files, and then compares them to expected results using `git diff`. Here are some reasons I like it:
- Specify complicated, multiline text expectations without fiddling with escape characters in test code.
- Clearly differentiate between stdout and stderr.
- Specify success/failure exit code expectations, or by default expect zero and no stderr output, or some stderr expectation and a nonzero exit code.
- Tests are run and test output is placed in a dedicated subdirectory of `_build` for easy inspection when tests fail.
- Test cases can inherit from prototype cases.

IOTest is available via pip for easy distribution. Alternatively, the script can be freely copied into a project; there is a single python dependency (pithy utility library), also available through pip.


# License

iotest dedicated to the public domain. It is written and maintained by George King.


# Issues

Please file issues to the github repository: github.com/gwk/pithy.


# Usage

To run all tests in the `test` directory:
$ iotest test/

iotest will look for test cases, which are indicated by the presence of a `.iot`, `.out`, or `.err` file. The filename stem (the part before dot/extension) indicates the name of the test case. This is then used to find a test executable with the matching stem. For example, if we have a test case file `thing.iot` and corresponding executable file `thing.py`, iotest will run `thing.py` and compare its output to the expectations specified in `thing.iot`. If there is more than one test case file, e.g. `thing.iot` and `thing.err`, then they will be combined together as long as they do not conflict (in other words, `thing.iot` cannot also specify a stderr expectation).

Useful command-line options:
- `-fail-fast`: stop on the first failing test.
- `-interactive`: when a test fails, prompt to overwrite the expectation file (`.out`, `.err`, etc.) with the actual output.
- `-dbg`: print the command, working directory, and environment for each case; implies `-fail-fast`.
- `-parse-only`: parse all test cases and report the count without running them.
- `-retest`: rerun only tests that failed in the previous run.
- `-coverage`: trace test coverage using `coven`.
- `-build-dir DIR`: use an alternate build directory (default `_build`).


# Writing Test Cases

A test case is the set of sibling files that share a single path stem. The stem names the case; the various extensions supply the executable, the configuration, and the output expectations. `iotest` must be run from within a project, identified by a `.git` directory or a `.project-root` file at the root.

## Case files

The files that make up a case are distinguished by extension. At least one of these three must be present to signify a test case:
- `.iot`: the test configuration, written as a Python literal (see below). Optional; a case can be defined entirely by its other files.
- `.out`: the expected text on stdout.
- `.err`: the expected text on stderr.

A source file with the same stem and no standard extension (e.g. `thing.py`, `thing.sh`, `thing.swift`) is the default program to run, but does not itself signify a test case.

The three files are merged, and it is an error for them to conflict: if a `thing.out` file exists, then `thing.iot` must not also specify an `out_val` or `out_path`. The same goes for `.err`.

The output extensions may carry an additional trailing extension so that editors and viewers recognize the format, e.g. `thing.out.svg` or `thing.out.json`. The standard extension must come first.

The simplest possible case is a source file plus an empty iot or expectation file. For example, a script `true.py` next to an empty `true.iot` or `true.out` runs the script and expects a clean exit (code 0) with no output.

### Empty `.iot` files

An empty (or all-whitespace) `.iot` file is meaningful and common: it contributes no configuration of its own, but it *declares that the stem is a test case*. All of the case's behavior is then inherited from the applicable defaults: the `_default.iot` prototype chain (see Default cases below) and any parameterized template whose pattern matches the stem (see Parameterized cases). This is why an empty `.iot` next to a source file is not a no-op and does not necessarily mean "run and expect success" — for example, a directory whose `_default.iot` sets `'interpreter': 'legs'` will run every empty-`.iot` case through that interpreter. To understand what an empty `.iot` does, read the `_default.iot` files from the project root down to the case's directory, plus any `%`-parameterized `.iot` in the same directory.

## The `.iot` configuration file

An `.iot` file contains a single Python literal, parsed with `ast.literal_eval` (so it is data, not executed code, and may contain `#` comments). It is normally a dictionary mapping configuration keys to values. For example:

```
{
  'args': '0 "std out" "std err"',
  'code': 0,
  'out_val': 'std out\n',
  'err_val': 'std err\n',
}
```

An empty file, or `{}`, is a valid case that simply runs the matching program and expects success.

Keys may be written with either hyphens or underscores; `out-mode` and `out_mode` are equivalent. The key `in` is accepted as an alias for stdin input.

### Configuration keys

| Key | Type | Meaning |
| --- | --- | --- |
| `args` | str or list of str | Arguments passed to the program under test. A string is expanded then split with shell quoting rules; a list is expanded element-wise. |
| `cmd` | str or list of str | The command to run, overriding the default of running the matching source file. |
| `code` | int or `...` | Expected exit code. Defaults to 0, or 1 if a stderr expectation is present. `...` (Ellipsis) accepts any code. |
| `compile` | list of (str or list of str) | Commands to run before the test; see Compile steps. |
| `compile_timeout` | positive int | Timeout in seconds for compile commands. |
| `coverage` | str or list of str | Names of modules to include in coverage analysis (with `-coverage`). |
| `desc` | str | A human-readable description, printed when the case fails. |
| `env` | dict of str | Environment variables for the test process; values are expanded. |
| `in` / `in_` | str | Text supplied to the program on stdin. |
| `interpreter` | str or list of str | Interpreter prepended to the command, e.g. `python3`. |
| `interpreter_args` | str or list of str | Arguments for the interpreter (requires `interpreter`). |
| `links` | str, set of str, or dict of str | Symlinks to create inside the test directory; see Symlinks. |
| `out_mode`, `err_mode` | str | Comparison mode for stdout/stderr; see Comparison modes. |
| `out_val`, `err_val` | str | Inline expected stdout/stderr text. |
| `out_path`, `err_path` | str | Path to a file holding the expected stdout/stderr (alternative to `*_val`). |
| `files` | dict | Expectations for additional output files; see Additional file expectations. |
| `skip` | bool | If true, the case is reported as skipped and not run. |
| `timeout` | positive int | Timeout in seconds for the test process (default 4). |

## What gets run

The command for a case is assembled in this order: `interpreter`, then `interpreter_args`, then either `cmd` or the default program, then `args`.

If `cmd` is not given, the default program is chosen as follows:
- If `compile` steps are present, the compiled product `./<name>` is run.
- Otherwise, the single sibling source file (the file sharing the stem with no standard extension) is symlinked into the test directory and run as `./<name>`.
- It is an error to have neither a `cmd` nor exactly one default source file.

## Standard output and error expectations

Stdout and stderr are each captured to a file and compared against an expectation. An expectation can be given three ways, which are mutually exclusive for a given stream:
- a sibling `.out` / `.err` file,
- an inline `out_val` / `err_val` string,
- an `out_path` / `err_path` pointing at a file elsewhere.

If no expectation is given for a stream, it is expected to be empty.

### Comparison modes

`out_mode` and `err_mode` (and the `mode` of a `files` entry) select how the captured output is compared, default `equal`:

- `equal`: exact string equality. On failure a colorized `git diff` is shown.
- `contain`: passes if the expected string occurs anywhere in the output.
- `ignore`: the output is not checked at all.
- `match`: the expectation is a line-oriented pattern. Each line of the expectation must begin with a two-character prefix:
  - `| ` (literal): the rest of the line must match exactly.
  - `~ ` (regex): the rest of the line is a Python regular expression matched against the full output line.
  - A bare `|` or `~` on an otherwise empty line matches an empty line (the trailing space may be omitted).

  Every output line must be matched by exactly one pattern line, and vice versa. Example:

  ```
  {
    'out_mode': 'match',
    'out_val': '''\
  ~ BUILD: .+/_build
  | DIR: iotest_/test/basic
  | NAME: env
  ~ PROJ: .+/pithy
  ''',
  }
  ```

## Variable expansion

String values are expanded with `string.Template` semantics (`$NAME` or `${NAME}`) against the test environment before use. iotest defines these variables for every case:

- `$BUILD`: the build directory.
- `$DIR`: the directory portion of the case stem.
- `$NAME`: the case name (final path component of the stem).
- `$PROJ`: the absolute project root.
- `$SRC`: the default source path, or `NONE` if there is not exactly one.
- `$STEM`: the full case stem.

Variables defined in the case `env` are also available for expansion. Selected variables from the surrounding environment (`HOME`, `LANG`, `PATH`, `PYTHONPATH`, `NODE_PATH`, `SDKROOT`, `TMPDIR`) are passed through to the test process automatically.

## Symlinks

`links` creates symlinks inside the per-case test directory, pointing back at files in the project. This is how a test gains access to its input fixtures. Link sources are resolved relative to the project root and expanded:

- a string links a single path under its own basename,
- a set links each path under its basename,
- a dict maps each source path to an explicit link name.

```
{
  'cmd': 'legs $NAME.legs -output $NAME',
  'links': { '$STEM.legs' },
}
```

## Compile steps

`compile` is a list of commands run in the test directory before the test command. Each command is a string (split with shell quoting) or a list of arguments. If any compile step fails, the case fails and its output is shown. When compile steps are present and no `cmd` is given, the test runs the compiled product `./<name>`.

```
{
  'compile': ['basic/compile.py'],
  'links': {'iotest_/test/basic'},
  'out_val': 'output from compiled script.\n',
}
```

## Additional file expectations

Besides stdout and stderr, a test can assert the contents of files it writes into its test directory, via `files`. Each key is the output file path; each value is an expectation dictionary accepting `mode`, `val`, and `path` (the same semantics as the standard streams). Do not use `files` for `out` or `err`; use the dedicated keys instead.

```
{
  'files': {
    'result.json': {'mode': 'equal', 'path': 'expected/result.json'},
  },
}
```

## Multicases

If an `.iot` file contains a list of dictionaries instead of a single dictionary, it defines a series of subcases named `<stem>.0`, `<stem>.1`, and so on. Subcases run in order and share a test directory: only the first subcase clears the directory, so later subcases may depend on state left by earlier ones. The `_default` case may not be a multicase.

```
[ { 'cmd': 'true' },
  { 'cmd': 'false', 'code': 1 },
]
```

## Parameterized cases

A stem containing a `%` formatter (see pithy's filename formatters) is a template that applies to multiple concrete cases by name. For example, a file `param-%s.iot` supplies configuration to any case whose stem matches `param-*` (such as `param-out` and `param-err`). The substrings captured by the formatter are available as default arguments to the matched program. A matching case still needs to be declared by one of its own files (often just an empty `.iot`, or a `.out` / `.err` expectation); the parameterized template fills in the configuration, much like a `_default.iot` but scoped by name pattern rather than by directory. A concrete case with its own configuration overrides the template for the keys it sets. iotest warns if a parameterized template is never used.

## Default (prototype) cases

A file named `_default.iot` provides configuration inherited by every case in its directory and all subdirectories. Defaults are collected from the project root down to the case directory, so nested `_default.iot` files refine those above them, and an individual case's own configuration overrides the inherited defaults. This is the place for shared settings such as a common `cmd`, `interpreter`, `links`, `timeout`, or `coverage` list.

Because of this inheritance, a case's `.iot` file only needs to specify what differs from the defaults; an empty `.iot` inherits the defaults wholesale (see Empty `.iot` files above). A `_default.iot` is itself a prototype, not a runnable case, and may not be a multicase.

```
{
  'cmd': 'legs $NAME.legs -output $NAME',
  'links': { '$STEM.legs' },
  'timeout': 15,
}
```

## Where tests run

Each case runs in its own directory under the build directory (default `_build`), mirroring the case's path. stdout and stderr are written there as `<name>.out` and `<name>.err`, and any other files the program writes land there too. These outputs are left in place after a run so that failures can be inspected, and a `.failed` marker file is written next to the outputs of a failing case to support `-retest`.
