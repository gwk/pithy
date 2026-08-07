// Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

//! The crate root, which Cargo finds via the `[lib] path` setting in Cargo.toml rather than at the default `src/lib.rs`.
//! It lives inside the Python package so that each module's Rust sources sit beside its `.pyi` interface.
//!
//! A crate builds exactly one extension module, so every native function is exported flat from `_pyrrhus`;
//! the modules `pyrrhus.byte_utils` and `pyrrhus.str_utils` are ordinary `.py` files that re-export from it.
//! Each interface is declared by a `.pyi` and implemented in a hand-written module here;
//! the wrappers for all of them are generated into the single `_pyrrhus.gen.rs`.

mod _pyrrhus;
mod byte_utils;

// Resolves to `str_utils/mod.rs`, the Rust equivalent of the subpackage's `__init__.py`.
mod str_utils;
