# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import TypeVar


_T = TypeVar('_T')

def unwrap(optional:_T|None) -> _T:
  if optional is None: raise ValueError('unexpected None')
  return optional
