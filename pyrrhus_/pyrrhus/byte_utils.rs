// Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

//! Implementations of the interface declared in `byte_utils.pyi`.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

pub fn sum_bytes(data: &[u8]) -> PyResult<i64> {
  Ok(data.iter().map(|&b| i64::from(b)).sum())
}

pub fn find_byte(data: &[u8], byte: i64) -> PyResult<Option<i64>> {
  let byte = u8::try_from(byte).map_err(|_| PyValueError::new_err("byte must be in the range 0-255"))?;
  Ok(data.iter().position(|&b| b == byte).map(|i| i as i64))
}
