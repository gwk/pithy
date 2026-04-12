# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Callable, Iterable, overload, SupportsIndex, TypeVar


_T = TypeVar('_T')


class DefaultList(list[_T]):
  '''
  A subclass of `list` that adds default elements produced by a factory function
  when an out-of-bounds element is accessed or set past the end.
  The factory function takes the array index as a its sole parameter.
  '''

  def __init__(self, factory:Callable[[int], _T], iterable:Iterable[_T]=(), fill_length:int=0):
    super().__init__(iterable)
    self.factory = factory
    for i in range(fill_length):
      self.append(factory(i))

  @overload
  def __getitem__(self, index: SupportsIndex, /) -> _T: ...

  @overload
  def __getitem__(self, index: slice, /) -> list[_T]: ...

  def __getitem__(self, index, /):
    if isinstance(index, slice):
      end = len(self) if index.stop is None else index.stop
    else:
      end = index + 1
    for i in range(len(self), end):
      self.append(self.factory(i))
    return super().__getitem__(index)


  @overload
  def __setitem__(self, index: SupportsIndex, value: _T, /) -> None: ...

  @overload
  def __setitem__(self, index: slice, value: Iterable[_T], /) -> None: ...

  def __setitem__(self, index, value, /):
    if isinstance(index, slice):
      end = len(self) if index.stop is None else index.stop
    else:
      end = index + 1
    for i in range(len(self), end):
      self.append(self.factory(i))
    super().__setitem__(index, value)


  def __repr__(self) -> str:
    return '{}({}, {})'.format(type(self).__qualname__, self.factory, super().__repr__())
