# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
simple bar charts with unicode block chars.
'''

from enum import Enum
from math import log2
from typing import Mapping, Optional


# Horizontal block chars.
full_block = '\u2588'
blocks = (
  ' '
  '\u258f' # left one eighth block.
  '\u258e' # left one quarter block.
  '\u258d' # left three eighths block.
  '\u258c' # left half block.
  '\u258b' # left five eighths block.
  '\u258a' # left three quarters block.
  '\u2589' # left seven eighths eighths block.
  '\u2588'  # full block.
)


def bar_str(ratio: float, width: float, pad_right=False) -> str:
  'create a string of block characters for the given ratio and width.'
  if ratio > 1:
    return '*' * width

  index           = int(ratio * width * 8)  # quantize the ratio
  solid_count     = index // 8              # number of filled blocks
  fraction_index  = index % 8
  solid           = full_block * solid_count # string of solid blocks
  fraction        = blocks[fraction_index] if fraction_index else '' # fraction char string.
  pad             = (' ' * (width - (solid_count + len(fraction)))) if pad_right else ''

  return '{}{}{}'.format(solid, fraction, pad)


def chart(name: str, val: float, ratio: float, name_width: int, val_width: int, bar_width: int, suffix: str=None):
  'create a string for a single line of a chart.'
  bar = bar_str(ratio=ratio, width=bar_width, pad_right=bool(suffix))
  return '  {name:<{name_width}} : {val:>{val_width}}  {ratio:.3f} {bar}{suffix}'.format(
    name=name, name_width=name_width, val=val, val_width=val_width, ratio=ratio, bar=bar, suffix=suffix)


class ChartMode(Enum):
  '''
  Rendering modes:

  normalized: Scale the values so that the longest bar (greater than zero) spans the full width of the chart.

  log2: using the log of each value, normalize the bars.

  total: Scale the values so that the sum of all the bars would span the full width of the chart.

  cumulative: Each value is summed with all previous values, and scaled by the sum of all values.

  ratio: each value is a pair of values. Values with zero denominator are ignored; positive ratios are scaled to the width of the chart.
  '''
  normalized, log2, total, cumulative, ratio = range(5)


def chart_map(m: Mapping, mode:ChartMode=ChartMode.normalized, threshold=0, sort_by_val=False, width=64):
  '''
  create a chart from a map, where values are either integers or pairs of integers
  (for ChartMode.ratio).
  threshold is a minimum denominator count for ratios, and a minimum ratio otherwise.
  '''

   # rows are of form (sortKey, name, val, ratio). key can be of any type; name and val must be strings.
  rows = []
  total = 0
  cum = 0
  min_val = 0
  max_val = 0
  rng = 0

  if m and mode in (ChartMode.total, ChartMode.cumulative):
    total = sum(m.values())

  elif m and mode is ChartMode.normalized:
    max_val = max(m.values())
    if max_val <= 0:
      max_val = 1 # hack to prevent divide by zero.

  elif m and mode is ChartMode.log2:
    min_val = log2(min(m.values()))
    max_val = log2(max(m.values()))
    rng = max_val - min_val
    if rng <= 0: raise ValueError(min_val)

  for k, v in sorted(m.items()):

    if mode is ChartMode.normalized:
      r = v / max_val
      if r < threshold:
        continue
      val = '{:,}'.format(v)

    elif mode is ChartMode.log2:
      r = (log2(v) - min_val) / rng
      if r < threshold:
        continue
      val = '{:,}'.format(v)

    elif mode is ChartMode.total:
      r = v / max(total, 1)
      if r < threshold:
        continue
      val = '{:,}'.format(v)

    elif mode is ChartMode.cumulative:
      cum += v
      r = cum / total
      if r > 1 - threshold:
        continue
      val = '{:,}'.format(cum)

    elif mode is ChartMode.ratio:
      if v[0] < threshold or v[1] <= 0:
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

  lines = [chart(n, v, r, name_width=name_width, val_width=val_width, bar_width=width, suffix='\n')
    for sk, n, v, r in rows]

  return ''.join(lines)



if __name__ == '__main__':
  for mode in (ChartMode.normalized, ChartMode.total, ChartMode.cumulative):
    m = { i : i for i in range(16) }
    print('mode:', mode)
    print(chart_map(m, mode=mode))

  print('mode:', ChartMode.ratio)
  print(chart_map({ i: (i - 1, i) for i in range(16) }, mode=ChartMode.ratio))
