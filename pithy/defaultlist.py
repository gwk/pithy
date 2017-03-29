# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Callable, Generic, Iterable, TypeVar, Union


T = TypeVar('T')


class DefaultList(list, Generic[T]):
  '''
  A subclass of `list` that adds default elements produced by a factory function
  when an out-of-bounds element is accessed.
  '''

  def __init__(self, factory: Callable[[], T], iterable: Iterable[T]=(), fill_length=0) -> None:
    super().__init__(iterable)
    self.factory = factory
    for i in range(0, fill_length):
      self.append(self.factory())

  def __getitem__(self, index: Union[int, slice]):
    if isinstance(index, slice):
      end = 0 if index.stop is None else index.stop
    else:
      end = index
    while len(self) <= end:
      self.append(self.factory())
    return super().__getitem__(index)

  def __repr__(self) -> str:
    return '{}({}, {})'.format(type(self).__qualname__, self.factory, super().__repr__())
