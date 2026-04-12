# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any, Generic, Iterator, Mapping, TypeVar


_K = TypeVar('_K')
_V = TypeVar('_V')

'''

'''


class EmptyMapping(Generic[_K,_V], Mapping[_K,_V]):
  '''
  A generic mapping type that is always empty.
  This is useful for creating a default value for a mapping property, e.g. in a dataclass or parameter default.
  '''

  def __len__(self) -> int: return 0

  def __iter__(self) -> Iterator[_K]: return iter([])

  def __getitem__(self, key: _K) -> _V: raise KeyError(key)

  def __contains__(self, key:Any) -> bool: return False

  def __bool__(self) -> bool: return False

  def __repr__(self) -> str: return '{}()'.format(type(self).__name__)
