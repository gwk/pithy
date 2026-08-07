# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# This file is the source of truth for `pyrrhus.byte_utils`, which is laid out as a single module:
# the interface, the re-export shim and the implementations sit side by side as `byte_utils.{pyi,py,rs}`.
# The pyo3 wrappers are generated into the crate-wide `_pyrrhus.gen.rs`.
# Compare with `str_utils`, which is laid out as a package directory.

'''
Utilities for bytes, implemented in Rust.
'''

def sum_bytes(data:bytes) -> int:
  'Return the sum of the byte values of `data`.'

def find_byte(data:bytes, byte:int, /) -> int|None:
  'Return the index of the first occurrence of `byte` in `data`, or None if it is not present.'
