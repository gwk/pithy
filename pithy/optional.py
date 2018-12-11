# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Optional, TypeVar


_T = TypeVar('_T')

def unwrap(optional:Optional[_T]) -> _T:
  if optional is None: raise ValueError('unexpected None')
  return optional
