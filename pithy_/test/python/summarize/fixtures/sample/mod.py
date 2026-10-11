'''
A sample module.
It has a multi-line docstring.
'''

from dataclasses import dataclass
from typing import overload


type Pair = tuple[int,int]

limit = 10

table = {
  'a': 1,
  'b': 2,
}

_private_const = 'hidden'


def plain(x:int) -> int:
  'Return x doubled.'
  return x * 2


def undocumented(a, b): return a + b


def multi_line_sig(a:int,
  b:str) -> str:
  '''
  Join a and b.

  The blank line above is preserved.
  '''
  def inner() -> None: pass
  return f'{a}{b}'


@overload
def over(x:int) -> int: ...
@overload
def over(x:str) -> str: ...
def over(x): return x


async def fetch(url:str) -> bytes:
  'Fetch a url.'
  return b''


def _helper() -> None: pass


@dataclass
class Point:
  'A point.'
  x:int
  y:int = 0

  def norm(self) -> float:
    'The L1 norm.'
    return abs(self.x) + abs(self.y)

  @property
  def is_origin(self) -> bool: return self.x == 0 and self.y == 0

  @staticmethod
  def _secret() -> None:
    'Private method.'

  class Nested:
    'Nested class.'
    def method(self) -> None: pass


if limit > 5:
  def conditional() -> None:
    'Defined conditionally.'
else:
  def conditional() -> None: pass
