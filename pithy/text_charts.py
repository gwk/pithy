# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from enum import Enum
from typing import Iterable, Mapping, Union


vertical_bars = ' ' + ''.join(chr(i) for i in range(0x2581, 0x2589))

horizontal_bars = (
  ' '
  '\u258f' # Left one eighth block.
  '\u258e' # Left one quarter block.
  '\u258d' # Left three eighths block.
  '\u258c' # Left half block.
  '\u258b' # Left five eighths block.
  '\u258a' # Left three quarters block.
  '\u2589' # Left seven eighths eighths block.
  '\u2588' # Full block.
)

full_block = '\u2588'

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


class ChartMode(Enum):
  Normalized, Total, Cumulative, Ratio = range(4)

Normalized, Total, Cumulative, Ratio = ChartMode


def chart_items(m:Mapping, mode=ChartMode.Normalized, threshold=0, sort_by_val=False, width=64) -> str:
  '''
  create a chart from a map, where values are either integers or pairs of integers (for ChartModeRatio).
  threshold is a minimum denominator count for ratios, and a minimum ratio otherwise.
  '''

  # rows are of form (sortKey, name, val, ratio). key can be of any type; name and val must be strings.
  rows = []

  if m and mode in (ChartMode.Total, ChartMode.Cumulative):
    total = sum(m.values())
    if mode is ChartMode.Cumulative:
      cum = 0

  elif m and mode is ChartMode.Normalized:
    max_val = max(m.values())
    if max_val <= 0:
      max_val = 1 # hack to prevent divide by zero.

  for k, v in sorted(m.items()):

    if mode is ChartMode.Normalized:
      r = v / max_val
      if r < threshold:
        continue
      val = '{:,}'.format(v)

    elif mode is ChartMode.Total:
      r = v / max(total, 1)
      if r < threshold:
        continue
      val = '{:,}'.format(v)

    elif mode is ChartMode.Cumulative:
      cum += v
      r = cum / total
      if r > 1 - threshold:
        continue
      val = '{:,}'.format(cum)

    elif mode is ChartMode.Ratio:
      if v[0] == 0 or v[1] < threshold:
        continue
      r = v[0] / v[1]
      val = '{:,}/{:,}'.format(*v)


    sort_key = r if sort_by_val else k
    row = (sort_key, str(k), val, r)
    rows.append(row)

  if not rows:
    return ''

  rows.sort(reverse=sort_by_val)

  name_width = max(len(r[1]) for r in rows)
  val_width  = max(len(r[2]) for r in rows)

  lines = [chart_line(n, v, r, name_width=name_width, val_width=val_width, bar_width=width, suffix='\n') for sk, n, v, r in rows]

  return ''.join(lines)


def chart_line(name:str, val:str, ratio:float, name_width:int, val_width:int, bar_width:int, suffix='') -> str:
  'create a string for a single line of a chart.'
  n = f'{name:<{name_width}}'
  v = f'{val:>{val_width}}'
  b = bar_str(ratio, bar_width, pad_right=bool(suffix))

  return '  {} : {}  {:.3f} {}{}'.format(n, v, ratio, b, suffix)


def bar_str(ratio:float, width:int, pad_right=False) -> str:
  'create a string of block characters for the given ratio and width.'
  if ratio > 1:
    return '*' * width

  index = int(ratio * width * 8) # quantize the ratio
  solid_count = index // 8 # number of filled blocks
  fraction_index = index % 8
  solid = full_block * solid_count # string of solid blocks
  fraction = horizontal_bars[fraction_index] if fraction_index else '' # fraction char string
  pad = (' ' * (width - (solid_count + len(fraction)))) if pad_right else ''

  return f'{solid}{fraction}{pad}'



if __name__ == '__main__':
  for mode in (ChartMode.Normalized, ChartMode.Total, ChartMode.Cumulative):
    print(mode)
    m = { i : i for i in range(32) }
    print(chart_items(m, mode=mode))
