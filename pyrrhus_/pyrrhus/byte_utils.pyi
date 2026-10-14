# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# This file is the source of truth for `pyrrhus.byte_utils`, which is laid out as a single module:
# the interface, the re-export shim and the implementations sit side by side as `byte_utils.{pyi,py,rs}`.
# The pyo3 wrappers are generated into the crate-wide `_pyrrhus.gen.rs`.
# Compare with `str_utils`, which is laid out as a package directory.

'''
Utilities for searching and summing bytes, implemented in Rust.

Inputs are Python bytes objects. Positions are zero-based byte offsets.
'''

_context_keywords_:list[str] = ['byte search', 'bytes.find', 'sum']


def sum_bytes(data:bytes) -> int:
  'Return the sum of the byte values of `data`.'

def find_byte(data:bytes, byte:int, /) -> int|None:
  '''
  Return the index of the first occurrence of `byte` in `data`, or None if it is not present.

  `byte` must be between 0 and 255; other values in the signed 64-bit range raise ValueError.
  Integers outside that range raise OverflowError during argument conversion.
  '''
