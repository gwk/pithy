# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Iterable, Union


vertical_bars = ' ' + ''.join(chr(i) for i in range(0x2581, 0x2589))

_min = min
_max = max

_Num = Union[int,float]


def chart_seq_inline(values:Iterable[_Num], max:_Num=0) -> str:
  values = tuple(values)
  if not values: return ''
  if max <= 0:
    max = _max(values)
    if max <= 0: return '\u2592' * len(values) # Medium shade block.
  return ''.join(vertical_bars[int(0.5 + (8 * _max(0, _min(1, v/max))))] for v in values)
