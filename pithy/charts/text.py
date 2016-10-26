'''
simple bar charts with unicode block chars.
'''

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


def bar_str(ratio, width, pad_right=False):
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


def chart(name, val, ratio, name_width, val_width, bar_width, suffix=None):
  'create a string for a single line of a chart.'
  bar = bar_str(ratio=ratio, width=bar_width, pad_right=bool(suffix))
  return '  {name:<{name_width}} : {val:>{val_width}}  {ratio:.3f} {bar}{suffix}'.format(
    name=name, name_width=name_width, val=val, val_width=val_width, ratio=ratio, bar=bar, suffix=suffix)


( ChartModeNormalized,
  ChartModeTotal,
  ChartModeCumulative,
  ChartModeRatio,
) = range(4)


def chart_map(m, mode=ChartModeNormalized, threshold=0, sort_by_val=False, width=64):
  '''
  create a chart from a map, where values are either integers or pairs of integers
  (for ChartModeRatio).
  threshold is a minimum denominator count for ratios, and a minimum ratio otherwise.
  '''

   # rows are of form (sortKey, name, val, ratio). key can be of any type; name and val must be strings.
  rows = []

  if m and mode in (ChartModeTotal, ChartModeCumulative):
    total = sum(m.values())
    if mode is ChartModeCumulative:
      cum = 0

  elif m and mode is ChartModeNormalized:
    max_val = max(m.values())
    if max_val <= 0:
      max_val = 1 # hack to prevent divide by zero.

  for k, v in sorted(m.items()):

    if mode is ChartModeNormalized:
      r = v / max_val
      if r < threshold:
        continue
      val = '{:,}'.format(v)

    elif mode is ChartModeTotal:
      r = v / max(total, 1)
      if r < threshold:
        continue
      val = '{:,}'.format(v)

    elif mode is ChartModeCumulative:
      cum += v
      r = cum / total
      if r > 1 - threshold:
        continue
      val = '{:,}'.format(cum)

    elif mode is ChartModeRatio:
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

  lines = [chart(n, v, r, name_width=name_width, val_width=val_width, bar_width=width, suffix='\n') for sk, n, v, r in rows]

  return ''.join(lines)



if __name__ == '__main__':
  for mode in (ChartModeNormalized, ChartModeTotal, ChartModeCumulative):
    m = { i : i for i in range(16) }
    print('mode:', mode)
    print(chart_map(m, mode=mode))
