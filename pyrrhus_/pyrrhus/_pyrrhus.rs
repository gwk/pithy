// Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

//! Implementations of the interface declared in `_pyrrhus.pyi`.
//!
//! These are plain Rust functions over native types; the generated wrappers in `_pyrrhus.gen.rs` supply the pyo3
//! boilerplate and the argument conversions. Each function must match the declaration it implements,
//! which the assertions at the top of the generated file check.
//!
//! Every function returns `PyResult` so that any of them can start raising a Python exception
//! without a change to the declaration or the generated code.

use pyo3::exceptions::PyOverflowError;
use pyo3::prelude::*;

// The generated wrappers. `#[path]` is necessary because `.gen.rs` is not a legal module file name,
// and the module is not called `gen` because that is a reserved keyword in edition 2024.
#[path = "_pyrrhus.gen.rs"]
pub mod generated;

pub fn hello_from_bin() -> PyResult<String> {
  Ok("Hello from pyrrhus!".to_string())
}

pub fn add(a: i64, b: i64) -> PyResult<i64> {
  a.checked_add(b)
    .ok_or_else(|| PyOverflowError::new_err("integer addition overflowed"))
}

pub fn scale(values: Vec<f64>, factor: f64) -> PyResult<Vec<f64>> {
  Ok(values.into_iter().map(|v| v * factor).collect())
}
