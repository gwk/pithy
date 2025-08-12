# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import MutableSequence
from typing import Iterable, overload, TypeVar

from typing_extensions import Any


_El = TypeVar('_El', covariant=True)



class Stack[_El](MutableSequence[_El]):
  '''
  A mutable stack of elements.
  This is implemented as a list, which stores the elements in reverse order.
  '''
  _list:list[_El]


  def __init__(self, iterable:Iterable[_El]=()):
    self._list = list(iterable)
    self._list.reverse()


  def __len__(self) -> int:
    return len(self._list)


  def __repr__(self) -> str:
    items = list(self._list)
    items.reverse()
    return f'Stack({items})'


  def __eq__(self, other:Any) -> bool:
    return isinstance(other, Stack) and self._list == other._list

  @overload
  def __getitem__(self, index:int, /) -> _El: ...

  @overload
  def __getitem__(self, index:slice, /) -> MutableSequence[_El]: ...

  def __getitem__(self, index:int|slice) -> _El|MutableSequence[_El]:
    l = len(self._list)
    if isinstance(index, slice):
      raise NotImplementedError('Slicing is not supported.')
    return self._list[l - index - 1]


  @overload
  def __delitem__(self, index:int, /) -> None: ...

  @overload
  def __delitem__(self, index:slice, /) -> None: ...

  def __delitem__(self, index:int|slice) -> None:
    l = len(self._list)
    if isinstance(index, slice):
      raise NotImplementedError('Slicing is not supported.')
    del self._list[l - index - 1]


  @overload
  def __setitem__(self, index:int, value:Any, /) -> None: ...

  @overload
  def __setitem__(self, index:slice, value:Any, /) -> None: ...

  def __setitem__(self, index:int|slice, value:Any) -> None:
    l = len(self._list)
    if isinstance(index, slice):
      raise NotImplementedError('Slicing is not supported.')
    self._list[l - index - 1] = value


  def insert(self, index:int, value:Any, /) -> None:
    l = len(self._list)
    if index < 0:
      index += l
    self._list.insert(l - index - 1, value)


  def push(self, value:_El, /) -> None:
    self._list.append(value)


  def pop(self, index:int=0, /) -> _El:
    return self._list.pop(len(self._list) - index - 1)
