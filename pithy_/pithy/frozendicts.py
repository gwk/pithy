# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
A standard `frozendict` type will be introduced in Python 3.15: https://peps.python.org/pep-0814/.
In the meantime, this module provides a simple implementation.
'''

from collections.abc import Mapping
from types import GenericAlias, MappingProxyType
from typing import Any, ItemsView, Iterable, Iterator, KeysView, overload, Protocol, TypeVar, ValuesView


_KT = TypeVar('_KT')
_VT = TypeVar('_VT')
_VT_co = TypeVar('_VT_co', covariant=True)
_S = TypeVar('_S')
_T = TypeVar('_T')
_T1 = TypeVar('_T1')
_T2 = TypeVar('_T2')


class SupportsKeysAndGetItem(Protocol[_KT, _VT_co]):
    def keys(self) -> Iterable[_KT]: ...
    def __getitem__(self, key: _KT, /) -> _VT_co: ...


class frozendict(Mapping[_KT, _VT]):
  '''
  An immutable dictionary.
  '''

  @overload
  def __init__(self, initial:SupportsKeysAndGetItem[_KT,_VT]|Iterable[tuple[_KT,_VT]]=()) -> None: ...

  @overload
  def __init__(self, initial:SupportsKeysAndGetItem[str,_VT]|Iterable[tuple[str,_VT]], **kwargs:_VT) -> None: ...

  def __init__(self, initial:Mapping[_KT,_VT]|Iterable[tuple[_KT,_VT]]=(), **kwargs:_VT) -> None: # type: ignore[misc]
    self._mapping:MappingProxyType[_KT,_VT] = MappingProxyType(dict(initial, **kwargs))


  def __repr__(self) -> str:
    contents = ', '.join(f'{k!r}: {v!r}' for k, v in self._mapping.items())
    return f'frozendict({{{contents}}})'


  def __getitem__(self, key:_KT, /) -> _VT:
    return self._mapping[key]

  def __iter__(self) -> Iterator[_KT]:
    return iter(self._mapping)

  def __len__(self) -> int:
    return len(self._mapping)

  def __eq__(self, value: object, /) -> bool:
    if not isinstance(value, Mapping): return False
    return dict(self._mapping) == dict(value)

  def __hash__(self) -> int:
    return hash(frozenset(self._mapping.items()))

  def __class_getitem__(cls, item: Any) -> GenericAlias:
    return GenericAlias(cls, item)

  def copy(self) -> frozendict[_KT, _VT]:
    'Return a shallow copy of the frozendict.'
    return frozendict(self._mapping)


  @classmethod
  @overload
  def fromkeys(cls, iterable: Iterable[_T], value: None = None, /) -> frozendict[_T, Any]: ...

  @classmethod
  @overload
  def fromkeys(cls, iterable: Iterable[_T], value: _S, /) -> frozendict[_T, _S]: ...

  @classmethod
  def fromkeys(cls, iterable: Iterable[Any], value: Any = None, /) -> frozendict[Any, Any]:
    return cls((k, value) for k in iterable)


  def keys(self) -> KeysView[_KT]:
    return self._mapping.keys()

  def values(self) -> ValuesView[_VT]:
    return self._mapping.values()

  def items(self) -> ItemsView[_KT, _VT]:
    return self._mapping.items()


  @overload
  def get(self, key:_KT, /) -> _VT | None: ...

  @overload
  def get(self, key:_KT, default:_VT, /) -> _VT: ...

  @overload
  def get(self, key:_KT, default:_T, /) -> _VT|_T: ...

  def get(self, key:_KT, default:Any=None, /) -> Any:
    return self._mapping.get(key, default)


  def __reversed__(self) -> Iterator[_KT]:
    return reversed(self._mapping)

  def __or__(self, value: dict[_T1, _T2] | frozendict[_T1, _T2], /) -> frozendict[_KT|_T1, _VT|_T2]:
    return frozendict(self._mapping | dict(value))

  @overload
  def __ror__(self, value: dict[_T1, _T2], /) -> dict[_KT|_T1, _VT|_T2]: ...

  @overload
  def __ror__(self, value: frozendict[_T1, _T2], /) -> frozendict[_KT|_T1, _VT|_T2]: ...

  def __ror__(self, value: dict[_T1, _T2] | frozendict[_T1, _T2], /) -> dict[_KT|_T1, _VT|_T2] | frozendict[_KT|_T1, _VT|_T2]:
    if isinstance(value, frozendict):
      return frozendict(dict(value) | dict(self._mapping))
    return dict(value) | dict(self._mapping)
