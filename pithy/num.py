# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Numeric utilities.
'''

from typing import Sequence, Iterator, Union


Num = Union[int, float]


_set_attr = object.__setattr__


class NumRange(Sequence[Num]):

  start:Num
  stop:Num
  step:Num
  closed:bool
  _len:int

  def __init__(self, start:Num, stop:Num=None, step:Num=1, *, closed=False) -> None:
    if stop is None: # Imitate `range`; `start` is actually `stop`.
      _set_attr(self, 'start', 0)
      _set_attr(self, 'stop', start)
    else:
      _set_attr(self, 'start', start)
      _set_attr(self, 'stop', stop)
    _set_attr(self, 'step', step)
    _set_attr(self, 'closed', closed)
    dist = max(0, self.stop - self.start)
    steps = dist / step
    extra = 1 if (closed or steps % 1) else 0
    _set_attr(self, '_len', int(steps) + extra)

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
    raise AttributeError('readonly attributes')

  def __hash__(self) -> int:
    return hash(self.start)^hash(self.stop)^hash(self.step)^int(self.closed)

  def __eq__(self, other:object) -> bool:
    return isinstance(other, NumRange) and \
    self.start == other.start and self.stop == other.stop and self.step == other.step and self.closed == other.closed
