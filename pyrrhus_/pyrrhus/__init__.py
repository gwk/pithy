# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pyrrhus._pyrrhus import add, hello_from_bin, scale


_context_keywords_ = ['maturin', 'native rust extension', 'pyo3']


__all__ = ['add', 'hello', 'hello_from_bin', 'scale']


def hello() -> str:
  return hello_from_bin()
