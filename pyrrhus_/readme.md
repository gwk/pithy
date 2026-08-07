# Pyrrhus

Pyrrhus is a collection of Python utilities backed by Rust extensions.

Unlike the other packages in this repository, pyrrhus is a mixed Python/Rust project.
Both languages live in `pyrrhus/`, and [maturin](https://www.maturin.rs) builds the Rust into the `pyrrhus._pyrrhus`
extension module.

# Interface

Each `.pyi` file is the source of truth for one native module, and `craft-py-rust-ext` generates the pyo3 boilerplate
from it. This is the reverse of the usual pyo3 arrangement, in which the Rust source defines the interface
and the `.pyi` is written by hand to match it, where it can silently drift.

Every native module is three files:

* `M.pyi`: the interface. Hand-written; the source of truth, and the stub that type checkers use.
* `M.py`: generated. Re-exports the module's functions from the extension, which makes the module importable.
* `M.rs`: scaffolded if missing, then hand-edited. Plain Rust functions over native types, one per declaration.

A crate builds exactly one extension module, so the pyo3 wrappers for every interface generate into the single
`_pyrrhus.gen.rs`: one `#[pyfunction]` wrapper per declaration, plus the module registration. Do not edit it.

To change an interface, edit the `.pyi`, run `just gen-py-rust-exts`, then fill in the Rust implementation bodies.
The tool maintains the `.py` shims and creates missing `.rs` files with `todo!()` bodies (`mod.rs` for a package interface).
Existing Rust files are never rewritten: missing or textually different signatures produce stdout guidance with copyable skeletons.
Removed declarations are reported against the previous generated wrappers; their implementations are left for manual review.
The signature scan is advisory and does not resolve Rust macros or type aliases; compilation remains authoritative.
New implementation modules still need to be declared in `lib.rs`.
The generated file contains an assertion per function, so an implementation that does not match its declaration
fails to compile with an error that names the function.

The generated file is committed, because building the crate requires it.

Implementations return `PyResult` so that any of them can raise a Python exception without a change to the declaration.
Note that the Python types narrow in translation: `int` maps to `i64`, so an argument outside that range raises
`OverflowError` before the implementation is called. See the `craft-py-rust-ext` docstring for the full mapping.

# Layout

The extension module `pyrrhus._pyrrhus` is a single flat namespace holding every native function in the crate.
Each native module of the package is a generated `.py` that re-exports its functions from the extension.
`byte_utils` and `str_utils` are laid out differently on purpose, to show both shapes:

```
pyrrhus/
  __init__.py            The Python package root; re-exports the root functions.
  lib.rs                 The crate root. Declares the Rust modules; contains no interface of its own.
  _pyrrhus.pyi           The extension module: the root interface, and the stub for the whole extension.
  _pyrrhus.gen.rs        Generated: the pyo3 wrappers for every interface in the crate.
  _pyrrhus.rs            Implementations of the root interface.
  byte_utils.pyi         A native module as a single module: interface, shim and implementations side by side.
  byte_utils.py
  byte_utils.rs
  str_utils/             A native module as a package: a directory.
    __init__.pyi
    __init__.py
    mod.rs
```

`lib.rs` is Cargo's name for a crate root, and `mod.rs` is Rust's name for the root of a module whose sources are a
directory, so `__init__.pyi` and `mod.rs` are the two languages' spellings of the same idea. Cargo's default crate root
is `src/lib.rs`; `[lib] path` in Cargo.toml points it here instead, which Cargo supports and does not otherwise care
about. Rust would also accept the 2018-style pairing of a `str_utils.rs` file with a `str_utils/` directory, but that
puts the module root outside the directory it belongs to, next to the Python package rather than inside it.

Which shape to use is the same judgement as in pure Python: a directory once the module wants to be split into parts,
a single module until then.

## One Extension, Ordinary Modules

A crate builds exactly one extension module, and the import system resolves dotted names from files,
so a native module nested inside the extension would not be importable on its own:
`import pyrrhus.byte_utils` cannot resolve to an attribute of `pyrrhus._pyrrhus`.
So the extension does not nest. Every function is exported flat from `pyrrhus._pyrrhus`,
and each module's `.py` re-exports its share of them at the declared path.
To keep the flat namespace collision-free, the wrappers of a merged interface `n` are exported as `n__f`;
the shims re-export them under their declared names, so the prefixed form appears only in the private module,
in tracebacks and in profiles, where it is unambiguous.

For type checkers, each `.pyi` shadows the `.py` beside it, so the shims themselves are not normally checked;
`_pyrrhus.pyi` re-exports the merged declarations under their prefixed names in a `TYPE_CHECKING` block
so that the extension's stub is complete and the shims typecheck against it when opened directly.

Shims are generated in full and must not contain hand-written Python code.
Put Python helpers in separate modules; the generator currently treats every interface declaration as native.

# Dev

## Rust Toolchain

Building pyrrhus requires a stable Rust toolchain.
Because pyrrhus is a member of the repository's uv workspace, `uv sync --all-packages` builds it,
which means that a working `cargo` is required to set up any package in this repository.

On macOS, install rustup with `brew install rustup`; homebrew delivers the rustup manager only.
Then install and select the stable toolchain, which also installs the `cargo` and `rustc` shims into `~/.cargo/bin`:

```sh
rustup default stable
```

Confirm that `cargo --version` works before running `uv sync`.

## Building

`just develop-global` installs the workspace packages, including pyrrhus, into the global interpreter.
For a workspace venv, run `just develop-venv` and follow its activation instruction.

After editing Rust or an interface, run `just develop-rust`.
It regenerates wrappers and shims, then rebuilds and installs pyrrhus into the interpreter selected by `python3`.
Routine tests and checks do not synchronize environments or rebuild the extension automatically.

For workspace synchronization, uv's cache keys include `pyrrhus/**/*.rs`, `Cargo.toml`, `Cargo.lock`, and `pyproject.toml`.
A plain `uv sync` does not regenerate wrappers; use `just develop-rust` after interface changes.

Rust build products go to `_build/cargo` rather than `target`, per the `.cargo/config.toml` at the repository root.

To build a release wheel:

```sh
just build # Builds all packages.
uv build --package pyrrhus --out-dir pyrrhus_/dist # Or just this one.
```

Because the Rust sources live in the package directory, `tool.maturin.exclude` keeps them out of the wheel.
They stay in the sdist, which has to be able to build the extension.

Note that unlike the pure-Python packages, which produce a single `py3-none-any` wheel,
pyrrhus produces a platform-specific wheel. It is built against the CPython stable ABI (abi3),
so one wheel per platform covers all supported Python versions.
Publishing therefore requires building on each target platform.

`just publish` uploads the sdist and the wheel for the platform that it runs on;
an installation on any other platform builds from the sdist, which requires a Rust toolchain.
`just validate-published` selects the published wheel that matches the platform that it runs on.

## Versioning

The pure-Python packages declare `dynamic = ["version"]` and flit reads `__version__` from the package `__init__.py`.
Maturin instead reads the version from `Cargo.toml`, which is the source of truth for pyrrhus,
and which `just version pyrrhus` and the publish scripts read too.
Write it so that it is also a normalized Python version, because it appears in the distribution file names.

## Type Checking

Mypy cannot see into the compiled extension; the `.pyi` files declare its interface, as described above.
Each one is both the generator's input and the stub that type checkers use for the module at that path,
so a declaration cannot be right for one and wrong for the other.
