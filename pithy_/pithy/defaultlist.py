# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Callable, cast, Iterable, overload, SupportsIndex, TypeVar


_T = TypeVar('_T')


class DefaultList(list[_T]):
  '''
  A subclass of `list` that adds default elements produced by a factory function
  when an out-of-bounds element is accessed or set past the end.
  The factory function takes the array index as a its sole parameter.
  '''

  def __init__(self, factory:Callable[[int], _T], iterable:Iterable[_T]=(), fill_length:int=0):
    super().__init__(iterable)
    if not callable(factory): raise TypeError('factory must be callable')
    self.factory = factory
    for i in range(len(self), fill_length):
      self.append(factory(i))

  @overload
  def __getitem__(self, index:SupportsIndex, /) -> _T: ...

  @overload
  def __getitem__(self, index:slice, /) -> list[_T]: ...

  def __getitem__(self, index:SupportsIndex|slice, /) -> _T|list[_T]:
    if isinstance(index, slice):
      end = len(self) if index.stop is None else index.stop
    else:
      end = int(index) + 1
    for i in range(len(self), end):
      self.append(self.factory(i))
    return super().__getitem__(index)


  @overload
  def __setitem__(self, index:SupportsIndex, value:_T, /) -> None: ...

  @overload
  def __setitem__(self, index:slice, value:Iterable[_T], /) -> None: ...

  def __setitem__(self, index:SupportsIndex|slice, value:_T|Iterable[_T], /) -> None:
    if isinstance(index, slice):
      # `list` has rather weird behavior when the slice indices are out of bounds:
      # it appends the values to the end, regardless of any "gap" between len(self) and slc.start.
      # DefaultList instead fills up to slc.start, provided that slc.start is non-negative.
      if index.start is not None and index.start > len(self):
        for i in range(len(self), index.start):
          self.append(self.factory(i))
      super().__setitem__(index, cast(Iterable[_T], value))
    else:
      # If index is positive and out-of-bounds, then fill up to it.
      idx = int(index)
      if idx > len(self):
        for i in range(len(self), idx):
          self.append(self.factory(i))
      if idx == len(self): # super __setitem__ will fail with IndexError.
        self.append(cast(_T, value))
      else:
        super().__setitem__(index, cast(_T, value))


  def __repr__(self) -> str:
    return '{}({}, {})'.format(type(self).__qualname__, self.factory, super().__repr__())
