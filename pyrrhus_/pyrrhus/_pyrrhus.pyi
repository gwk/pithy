# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# This file is the source of truth for the extension module, which is `pyrrhus._pyrrhus` at runtime.
# `craft-py-rust-ext` generates `_pyrrhus.gen.rs` from it, together with every other `.pyi` in the package:
# `byte_utils.pyi` and `str_utils/__init__.pyi`. The implementations of the functions declared here live in `_pyrrhus.rs`.
# Run `just gen-py-rust-exts` after editing.

'''
Functions implemented in Rust.
'''

from typing import TYPE_CHECKING


# The extension is a single flat module holding every native function in the crate;
# the functions of a merged interface `n` are exported as `n__f`, so that interfaces cannot collide.
# These stub-only re-exports keep this stub complete, so that the `.py` modules that re-export from the extension
# typecheck against it. The guard matters because this file is exec'd at generation time, before the extension is built.
if TYPE_CHECKING:
  from pyrrhus.byte_utils import find_byte as byte_utils__find_byte, sum_bytes as byte_utils__sum_bytes
  from pyrrhus.str_utils import repeat as str_utils__repeat


def hello_from_bin() -> str:
  'Return a greeting from the Rust extension.'

def add(a:int, b:int) -> int:
  'Return the sum of `a` and `b`. Raises OverflowError if the sum does not fit in a signed 64-bit integer.'

def scale(values:list[float], *, factor:float=1.0) -> list[float]:
  'Return `values` multiplied by `factor`.'
