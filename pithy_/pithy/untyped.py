# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from typing import Any, Generic, Iterable, Iterator, Mapping, TypeVar


_T = TypeVar('_T')


class Immutable(Generic[_T]):
  'Untyped immutable object.'

  def __init__(self, /, __dict:Mapping[str,_T]|Iterable[tuple[str,_T]]={}, **kwargs:_T):
    vars(self).update(__dict)
    vars(self).update(kwargs)

  def __repr__(self) -> str:
    args = ', '.join(f'{k if _is_identifier(k) else repr(k)}={v!r}' for k, v in vars(self).items())
    return f'{type(self).__name__}({args})'

  def __getattr__(self, key:str) -> _T:
    return vars(self)[key] # type: ignore[no-any-return]

  def __setattr__(self, name:str, val:_T) -> None:
    raise AttributeError('Immutable instance attributes are readonly')

  def __delattr__(self, name:str) -> None:
    raise AttributeError('Immutable instance attributes are readonly')

  def __getitem__(self, key:str) -> _T:
    return vars(self)[key] # type: ignore[no-any-return]

  def __hash__(self) -> int:
    return hash(tuple(vars(self).items()))

  def __eq__(self, other:Any) -> bool:
    return type(self) == type(other) and vars(self) == vars(other)

  def __iter__(self) -> Iterator[_T]:
    return iter(vars(self).items()) # type: ignore[arg-type]


_identifier_re = re.compile(r'(?!\d)\w+')
_is_identifier = _identifier_re.fullmatch
