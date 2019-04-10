# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from abc import abstractmethod
from typing import Any, Generic, Iterable, Iterator, Sequence, TypeVar, Union
from typing_extensions import Protocol
from .default import Default


Num = Union[int, float]

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


_setattr = object.__setattr__


class NumRange(Sequence[Num]):

  start:Num
  stop:Num
  step:Num
  closed:bool
  _len:int

  def __init__(self, start:Num, stop:Num=None, step:Num=1, *, closed=False) -> None:
    if stop is None: # Imitate `range`; `start` is actually `stop`.
      _setattr(self, 'start', 0)
      _setattr(self, 'stop', start)
    else:
      _setattr(self, 'start', start)
      _setattr(self, 'stop', stop)
    _setattr(self, 'step', step)
    _setattr(self, 'closed', closed)
    dist = max(0, self.stop - self.start)
    steps = dist / step
    extra = 1 if (closed or steps % 1) else 0
    _setattr(self, '_len', int(steps) + extra)

  def __len__(self):
    return self._len

  def __getitem__(self, i:Union[int, slice]) -> Num: # type: ignore
    if isinstance(i, int):
      if i >= 0 and i >= self._len: raise IndexError(i)
      return self.start + self.step * (i if i >= 0 else (self._len+i))
    elif isinstance(i, slice):
      raise NotImplementedError('NumRange does not yet support extended slicing')

  def __iter__(self) -> Iterator[Num]:
    return (self.start + self.step * i for i in range(self._len))

  def __repr__(self):
    return '{}({}, {}, {})'.format(type(self).__name__, self.start, self.stop, self.step)

  def __setattr__(self, name:str, val:str) -> None:
    raise AttributeError('NumRange attributes are readonly')

  def __hash__(self) -> int:
    return hash(self.start)^hash(self.stop)^hash(self.step)^int(self.closed)

  def __eq__(self, other:object) -> bool:
    return isinstance(other, NumRange) and \
    self.start == other.start and self.stop == other.stop and self.step == other.step and self.closed == other.closed
