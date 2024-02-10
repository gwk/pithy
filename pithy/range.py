# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Hashable
from typing import Any, Iterator, Sequence, TypeVar

from .types import Comparable


Num = int|float


_setattr = object.__setattr__


class NumRange(Sequence[Num], Hashable):
  '''
  A range type that supports int and float boundaries.'
  '''

  start:Num
  stop:Num
  step:Num
  closed:bool
  _len:int

  def __init__(self, start:Num, stop:Num|None=None, step:Num=1, *, closed=False):
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

  def __getitem__(self, i:int|slice) -> Num: # type: ignore[override]
    if isinstance(i, int):
      if i >= 0 and i >= self._len: raise IndexError(i)
      return self.start + self.step * (i if i >= 0 else (self._len+i))
    elif isinstance(i, slice):
      raise NotImplementedError('NumRange does not support extended slicing')
    raise TypeError(f'NumRange indices must be integers; received: {i!r}')

  def __iter__(self) -> Iterator[Num]:
    return (self.start + self.step * i for i in range(self._len))

  def __repr__(self):
    return '{}({}, {}, {})'.format(type(self).__name__, self.start, self.stop, self.step)

  def __setattr__(self, name:str, val:str) -> None:
    raise AttributeError('NumRange attributes are readonly')

  def __hash__(self) -> int:
    return hash(self.start)^hash(self.stop)^hash(self.step)^int(self.closed)

  def __eq__(self, other:object) -> bool:
    return type(self) == type(other) and vars(self) == vars(other)


_B = TypeVar('_B', bound=Comparable) # A bound type.


def do_ranges_overlap(a:tuple[_B,_B], b:tuple[_B,_B]) -> bool:
  'Return whether the two ranges overlap.'
  return bool(a[0] < b[1] and b[0] < a[1])



def do_ranges_from_attrs_overlap(a:Any, b:Any, start_attr:str, end_attr:str) -> bool:
  '''
  Return whether the two object's ranges overlap, given the names of their start and end attributes.
  '''
  a_s = getattr(a, start_attr)
  a_e = getattr(a, end_attr)
  b_s = getattr(b, start_attr)
  b_e = getattr(b, end_attr)
  return bool(a_s < b_e and b_s < a_e)
