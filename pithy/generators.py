# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Generator
from typing import Generic, TypeVar


Y = TypeVar("Y")  # Yield.
S = TypeVar("S")  # Send.
R = TypeVar("R")  # Return.


class GenRes(Generic[Y, S, R]):
  '''
  A type that wraps a generator and saves its return value as `res`.
  Usage:
  ```
  gen = GenRes(gen_func())
  for item in gen: ...
  print(gen.res) # The return value of the generator.
  ```
  '''

  class _Sentinel(): pass
  _sentinel = _Sentinel()


  def __init__(self, gen:Generator[Y, S, R]):
    self.gen = gen
    self.res:R|GenRes._Sentinel = self._sentinel


  def __iter__(self) -> Generator[Y,S,R]:
    self.res = yield from self.gen
    return self.res
