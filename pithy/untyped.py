# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from typing import Any, Dict, Iterator, Tuple


_setattr = object.__setattr__


class Immutable:
  'Untyped immutable object.'

  def __init__(self, obj:Any=None, **kw:Any) -> None:
    if obj is not None:
      self.__dict__.update(obj)
    for k, v in kw.items():
      _setattr(self, k, v)

  def __repr__(self) -> str:
    args = ', '.join(f'{k if _is_identifier(k) else repr(k)}={v!r}' for k, v in vars(self).items())
    return f'{type(self).__name__}({args})'

  def __getattr__(self, key:str) -> Any:
    'This is defined to let the typechecker know that the class is untyped.'
    raise AttributeError(key)

  def __setattr__(self, name, val) -> None:
    raise AttributeError('Immutable instance attributes are readonly')

  def __delattr__(self, name) -> None:
    raise AttributeError('Immutable instance attributes are readonly')

  def __getitem__(self, key:str) -> Any:
    return getattr(self, key)

  def __hash__(self) -> int:
    h = 0
    for p in vars(self).items():
      h ^= hash(p)
    return h

  def __eq__(self, other:Any) -> bool:
    return type(self) == type(other) and vars(self) == vars(other)

  def __iter__(self) -> Iterator[Any]:
    return iter(vars(self).items())


_identifier_re = re.compile(r'(?!\d)\w+')
_is_identifier = _identifier_re.fullmatch
