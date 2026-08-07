// Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

//! Implementations of the interface declared in `__init__.pyi`.
//!
//! `mod.rs` is to Rust what `__init__.py` is to Python: the root of a module whose sources are a directory.
//! Rust also allows the 2018-style pairing of `str_utils.rs` with a `str_utils/` directory,
//! but that would put the module root outside the package directory it belongs to.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

pub fn repeat(s: &str, count: i64, sep: &str) -> PyResult<String> {
  let count = usize::try_from(count).map_err(|_| PyValueError::new_err("count must be nonnegative"))?;
  Ok(vec![s; count].join(sep))
}
