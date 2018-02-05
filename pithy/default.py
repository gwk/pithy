# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from enum import Enum
from typing import TypeVar, Union


T = TypeVar('T')


class Default(Enum):
  '''
  Singleton class and value to indicate a default parameter value,
  for cases where None is a meaningful user provided value.
  For example: `def f(x:Union[int, Default]=Default._): ...`

  see: https://www.python.org/dev/peps/pep-0484/#support-for-singleton-types-in-unions
  '''
  _ = 0


class Raise(Enum):
  '''
  Raise serves the same purpose as Default,
  but suggests that the default behavior is to raise an exception.
  '''
  _ = 0


RaiseOr = Union[Raise, T]
