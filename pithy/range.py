# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from abc import abstractmethod
from typing import Any, Generic, Iterable, Iterator, TypeVar, Union
from typing_extensions import Protocol
from .default import Default


_Step = TypeVar('_Step', contravariant=True)


_RangeBound = TypeVar('_RangeBound', bound='RangeBound')

class RangeBound(Protocol, Generic[_Step]):

  @abstractmethod
  def __lt__(self, other:Any) -> bool: ...

  @abstractmethod
  def __eq__(self, other:Any) -> bool: ...

  @abstractmethod
  def __add__(self:_RangeBound, other:_Step) -> _RangeBound: ...



_Bound = TypeVar('_Bound', bound=RangeBound)


class Range(Generic[_Bound, _Step], Iterable[_Bound]):

  def __init__(self, start:_Bound, stop:Union[_Bound,Default]=Default._, *, step:_Step, length:Union[_Step,Default]=Default._, closed=False) -> None:
    self.start = start
    self.step = step
    self.closed = closed
    if isinstance(stop, Default):
      if isinstance(length, Default): raise ValueError('Range requires either `stop` or `length` argument')
      try: self.stop = start + length
      except TypeError:
        # Because builtin types like DateTime do not correctly raise NotImplemented, we try reversing the operands manually.
        try: self.stop = length + start # type: ignore
        except ValueError as e: raise ValueError(f'Range stop calculation failed: start: {start!r}; length: {length!r}') from e
    else:
      self.stop = stop

  def __iter__(self) -> Iterator[_Bound]:
    pos = self.start
    stop = self.stop
    step = self.step
    while pos < stop:
      yield pos
      try: pos += step
      except TypeError:
        # Because builtin types like DateTime do not correctly raise NotImplemented, we try reversing the operands manually.
        try: pos = step + pos # type: ignore
        except ValueError as e: raise ValueError(f'Range step addition failed: position: {pos!r}; step: {step!r}') from e
    if self.closed:
      yield stop
