# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
A standard `frozendict` type will be introduced in Python 3.15: https://peps.python.org/pep-0814/.
In the meantime, this module provides a simple implementation.
'''

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, ItemsView, Iterable, Iterator, KeysView, overload, Protocol, TypeVar, ValuesView


_KT = TypeVar('_KT')
_KT_co = TypeVar('_KT_co', covariant=True)
_KT_contra = TypeVar('_KT_contra', contravariant=True)
_VT = TypeVar('_VT')
_VT_co = TypeVar('_VT_co', covariant=True)
_T1 = TypeVar('_T1')
_T2 = TypeVar('_T2')

class SupportsKeysAndGetItem(Protocol[_KT,_VT_co]):
    def keys(self) -> Iterable[_KT]: ...
    def __getitem__(self, key: _KT, /) -> _VT_co: ...


_DictConstructable = SupportsKeysAndGetItem[_KT,_VT_co]|Iterable[tuple[_KT,_VT_co]]


class frozendict(Mapping[_KT,_VT_co]):
  '''
  An immutable dictionary.
  '''

  @overload
  def __init__(self, initial:SupportsKeysAndGetItem[_KT,_VT_co]|Iterable[tuple[_KT,_VT_co]]=()) -> None: ...

  @overload
  def __init__(self, initial:SupportsKeysAndGetItem[str,_VT_co]|Iterable[tuple[str,_VT_co]], **kwargs:_VT_co) -> None: ...

  def __init__(self, initial:Mapping[_KT,_VT_co]|Iterable[tuple[_KT,_VT_co]]=(), **kwargs:_VT_co) -> None: # type: ignore[misc]
    self._mapping:MappingProxyType[_KT,_VT_co] = MappingProxyType(dict(initial, **kwargs))


  def __repr__(self) -> str:
    contents = ', '.join(f'{k!r}: {v!r}' for k, v in self._mapping.items())
    return f'frozendict({{{contents}}})'


  def __getitem__(self, key:_KT, /) -> _VT_co:
    return self._mapping[key]

  def __iter__(self) -> Iterator[_KT]:
    return iter(self._mapping)

  def __len__(self) -> int:
    return len(self._mapping)

  def __eq__(self, value: object, /) -> bool:
    if not isinstance(value, frozendict): return False
    return self._mapping == value._mapping

  def copy(self) -> frozendict[_KT, _VT_co]:
    'Return a shallow copy of the frozendict.'
    return frozendict(self._mapping)


  def keys(self) -> KeysView[_KT]:
    return self._mapping.keys()

  def values(self) -> ValuesView[_VT_co]:
    return self._mapping.values()


  def items(self) -> ItemsView[_KT, _VT_co]:
    return self._mapping.items()


  @overload
  def get(self, key:_KT, /) -> _VT_co | None: ...

  @overload
  def get(self, key:_KT, default:_T2, /) -> _VT_co|_T2: ...

  def get(self, key:_KT, default:Any=None, /) -> Any:
    return self._mapping.get(key, default)


  def __reversed__(self) -> Iterator[_KT]:
    return reversed(self._mapping)

  def __or__(self, value: Mapping[_T1, _T2], /) -> frozendict[_KT|_T1,_VT_co|_T2]:
    return frozendict(self._mapping | dict(value))

  def __ror__(self, value: Mapping[_T1,_T2], /) -> frozendict[_KT|_T1,_VT_co|_T2]:
    return frozendict(dict(value) | self._mapping)
