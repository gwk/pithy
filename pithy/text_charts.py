# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from enum import Enum
from typing import Any, Iterable, Mapping, Union


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


def chart_inline(values:Iterable[_Num], max:_Num=0, width:int=0) -> str:
  'Create an inline chart out of vertical fractional bar characters.'
  values = tuple(values)
  if not values: return ''
  if max <= 0:
    max = _max(values)
    if max <= 0: return '\u2592' * len(values) # Medium shade block.
  if width > 0:
    vals = list(values)
    step: float = len(vals) / width
    values = [vals[int(step*i)] for i in range(width)]
  return ''.join(vertical_bars[int(0.5 + (8 * _max(0, _min(1, v/max))))] for v in values)


class ChartMode(Enum):
  '''
  Rendering modes for text charts.
  Normalized: values are scaled by the maximum value.
  Total: values are scaled by the sum of all values.
  Cumulative: charted values are the accumulation of successive values, scaled by the sum of all values.

  '''
  Normalized, Total, Cumulative = range(3)

Normalized, Total, Cumulative = tuple(ChartMode)


def chart_items(data:Union[Mapping[Any,_Num],Iterable[tuple[Any,_Num]]], mode=ChartMode.Normalized, threshold=0.0,
 sort_by_val=False, reverse=False, val_width=0, val_prec=16, bar_width=64, show_ratio=False) -> str:
  '''
  Create a chart from a mapping or iterable of key/value pairs.
  Keys are converted to string labels.
  Values are numeric (int or float).
  `threshold` is a minimum ratio (a value determined by the mode); items below the threshold are omitted.
  '''

  if isinstance(data, Mapping):
    pairs = sorted(data.items())
  else:
    pairs = list(data)

  if not pairs: return ''

  # Rows are of form (ratio, key, val).
  rows:list[tuple[float,str,str]] = []

  match mode:

    case ChartMode.Normalized:
      max_val = max(p[1] for p in pairs)
      if max_val <= 0.0:
        max_val = 1.0 # Prevent divide by zero on all-zero values.
      for k, v in pairs:
        r = v / max_val
        if r < threshold: continue
        rows.append((r, str(k), f'{v:.{val_prec}}' if isinstance(v, float) else f'{v:,}'))

    case ChartMode.Total:
      total = float(sum(p[1] for p in pairs))
      if total <= 0.0:
        total = 1.0 # Prevent divide by zero on all-zero values.
      for k, v in pairs:
        r = v / total
        if r < threshold: continue
        rows.append((r, str(k), f'{v:.{val_prec}}' if isinstance(v, float) else f'{v:,}'))

    case ChartMode.Cumulative:
      total = float(sum(p[1] for p in pairs))
      if total <= 0:
        total = 1.0 # Prevent divide by zero on all-zero values.
      accum = 0
      for k, v in pairs:
        accum += v
        r = accum / total
        if r < threshold: continue
        rows.append((r, str(k), f'{accum:.{val_prec}}' if isinstance(v, float) else f'{accum:,}'))

    case _:
      raise ValueError(f'unknown ChartMode: {mode}')

  if sort_by_val:
    rows.sort(reverse=reverse)

  name_width = max(len(r[1]) for r in rows)
  val_width = val_width or max(len(r[2]) for r in rows)

  lines = [chart_line(n, v, r, name_width=name_width, val_width=val_width, bar_width=bar_width, show_ratio=show_ratio, suffix='\n')
    for r, n, v in rows]

  return ''.join(lines)


Ratio = tuple[int,int]

def chart_ratio_items(data:Union[Mapping[Any,Ratio],Iterable[tuple[Any,Ratio]]], threshold=0, sort_by_val=False,
 reverse=False, val_width=0, bar_width=64, show_ratio=False) -> str:
  '''
  Create a chart from a mapping or iterable of key/value pairs, where the values are pairs of integers representing a ratio.
  This is useful for displaying ratios where the denominator might be zero; zero denominators are treated as zero values.
  '''

  if isinstance(data, Mapping):
    pairs = sorted(data.items())
  else:
    pairs = list(data)

  if not pairs: return ''

  # Rows are of form (ratio, key, val).
  rows:list[tuple[float,str,str]] = []

  for k, (n, d) in pairs:
    if d == 0:
      r = 0.0
    else:
      r = n / d
    if r < threshold: continue
    rows.append((r, str(k), f'{n:,}/{d:,}'))


  if sort_by_val:
    rows.sort(reverse=reverse)

  name_width = max(len(r[1]) for r in rows)
  val_width = val_width or max(len(r[2]) for r in rows)

  lines = [chart_line(n, v, r, name_width=name_width, val_width=val_width, bar_width=bar_width, show_ratio=show_ratio, suffix='\n')
    for r, n, v in rows]

  return ''.join(lines)


def chart_line(name:str, val:str, ratio:float, name_width:int, val_width:int, bar_width:int, show_ratio:bool, suffix='') -> str:
  'create a string for a single line of a chart.'
  b = bar_str(ratio, bar_width)
  ratio_str = f'  {ratio:.3f}' if show_ratio else ''
  return f'  {name:<{name_width}} : {val:>{val_width}}{ratio_str} {b}{suffix}'


def bar_str(ratio:float, width:int) -> str:
  'create a string of block characters for the given ratio and width.'
  if ratio > 1:
    return full_block * width + '+'

  index = int(ratio * width * 8) # Quantize the ratio.
  solid_count = index // 8 # Number of filled blocks.
  fraction_index = index % 8
  solid = full_block * solid_count # String of solid blocks.
  fraction = horizontal_bars[fraction_index] if fraction_index else '' # Fraction char string.
  pad = (' ' * (width - (solid_count + len(fraction))))

  return f'{solid}{fraction}{pad}|'



if __name__ == '__main__':

  def examples() -> None:
    for mode in (ChartMode.Normalized, ChartMode.Total, ChartMode.Cumulative):
      print(mode)
      m = { i : i for i in range(16) }
      print(chart_items(m, mode=mode))

    for mode in (ChartMode.Normalized, ChartMode.Total, ChartMode.Cumulative):
      print('float values,', mode)
      mf = { i/3 : i/3 for i in range(16) }
      print(chart_items(mf, mode=mode, val_prec=6))

    print('sort_by_val=True')
    print(chart_items([('a', 3), ('b', 2), ('c', 1), ('d', 4), ('e', 0)], sort_by_val=True))


    mr = { (n, d) : (n, d) for d in range(4) for n in range(4) }
    print(chart_ratio_items(mr,))

  examples()
