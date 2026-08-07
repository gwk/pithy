# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# This file is the source of truth for `pyrrhus.str_utils`, which is laid out as a package directory:
# `__init__.pyi` is the interface, `__init__.py` is the re-export shim, and the Rust module root is `mod.rs`.
# The pyo3 wrappers are generated into the crate-wide `_pyrrhus.gen.rs`.
# Compare with `byte_utils`, which is laid out as a single module.

'''
Utilities for strings, implemented in Rust.
'''

def repeat(s:str, count:int, sep:str='') -> str:
  'Return `count` copies of `s`, joined by `sep`. Raises ValueError if `count` is negative.'
