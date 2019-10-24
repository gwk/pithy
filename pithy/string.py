# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'String utilities.'

import re
from decimal import Decimal
from string import Template
from typing import Any, Callable, Iterable, Iterator, List, Sequence, Tuple, TypeVar

_T = TypeVar('_T')


def render_template(template:str, **substitutions:Any) -> str:
  'Render a template using $ syntax.'
  t = Template(template)
  return t.substitute(substitutions)


def string_contains(string:str, query:str) -> bool:
  'Return True if string contains query.'
  return string.find(query) != -1


def clip_prefix(string:str, prefix:str, req=True) -> str:
  'Remove `prefix` if it is present, or raise ValueError, unless `req` is False.'
  if string.startswith(prefix):
    return string[len(prefix):]
  elif req:
    raise ValueError(string)
  return string


def clip_suffix(string:str, suffix:str, req=True) -> str:
  'Remove `suffix`if it is present, or raise ValueError, unless `req` is False.'
  if len(suffix) == 0: return string # need this case because string[:-0] == ''.
  if string.endswith(suffix):
    return string[:-len(suffix)]
  elif req:
    raise ValueError(string)
  return string


def replace_prefix(string:str, prefix:str, replacement:str, req=True) -> str:
  'Replace `prefix` if it is present, or raise ValueError, unless `req` is False.'
  if string.startswith(prefix):
    return replacement + string[len(prefix):]
  elif req:
    raise ValueError(string)
  return string


def replace_suffix(string:str, suffix:str, replacement:str, req=True) -> str:
  'Replace `suffix`if it is present, or raise ValueError, unless `req` is False.'
  if len(suffix) == 0: return string # need this case because string[:-0] == ''.
  if string.endswith(suffix):
    return string[:-len(suffix)] + replacement
  elif req:
    raise ValueError(string)
  return string


def clip_first_prefix(string:str, prefixes:Sequence[str], req=True) -> str:
  'Remove the first matching prefix in `prefixes` from `string`, or raise ValueError, unless `req is False`.'
  for p in prefixes:
    try:
      return clip_prefix(string, p, req=True)
    except ValueError:
      continue
  if req: raise ValueError(string)
  else: return string


def clip_common(strings:Sequence[str], prefix=True, suffix=True) -> Tuple[str,...]:
  if not strings: return ()
  if len(strings) == 1: return ('',)
  first = strings[0]
  min_len = min(len(s) for s in strings)
  i = 0
  if prefix:
    while i < min_len and all(s[i] == first[i] for s in strings):
      i += 1
  l = -1 # Last index.
  if suffix:
    l_term = i - min_len # The final negative index before we would clip everything from `i` to end.
    while l > l_term and all(s[l] == first[l] for s in strings):
      l -= 1
  return tuple(s[i:l] for s in strings)


def replace_first_prefix(string:str, prefixes:Sequence[Tuple[str,str]], req=True) -> str:
  'Replace the first matching prefix in `prefixes` from `string`, or raise ValueError, unless `req is False`.'
  for prefix, replacement in prefixes:
    try:
      return replace_prefix(string, prefix, replacement, req=True)
    except ValueError:
      continue
  if req:
    raise ValueError(string)
  return string


def find_and_clip_suffix(string:str, suffix:str, req=True) -> str:
  idx = string.find(suffix)
  if idx == -1:
    if req: raise ValueError(string)
    else: return string
  return string[:idx]


def indent_lines(lines:Iterable[str], depth=1) -> Iterator[str]:
  ind = '  '*depth
  for line in lines:
    nl = '' if line.endswith('\n') else '\n'
    yield f'{ind}{line}{nl}'


def iter_str(iterable:Iterable[str]) -> Iterable[str]:
  'Return the iterable unless it is a string, in which case return the single-element tuple of the string.'
  if isinstance(iterable, str): return (iterable,)
  return iterable


def iter_excluding_str(iterable:Iterable[_T]) -> Iterator[_T]:
  '''
  Often we want to handle all iterables in a particular way, except for str.
  There are two common reasons why:
  * because str should be treated as an atom/leaf value in a nested structure;
  * because the fact that elements of a str are themselves strings,
    which makes naive type-based recursion over sequences impossible.
  '''
  if isinstance(iterable, str):
    raise TypeError('iter_excluding_str explictly treats str as non-iterable type')
  return iter(iterable) # raises TypeError for non-iterables.


def pluralize(count:int, name:str, plural=None, spec='') -> str:
  'Return a string of format "{count} {name}s", with optional custom plural form and format spec.'
  if count == 1:
    n = name
  elif plural is None:
    n = name + 's'
  else:
    n = plural
  return '{count:{spec}} {n}'.format(count=count, spec=spec, n=n)


def format_nonempty(fmt:str, string:str) -> str:
  'format `string` into `format` unless `string` is empty.'
  return '' if (string == '') else fmt.format(string)

def prepend_to_nonempty(prefix:str, string:str) -> str:
  'prepend `prefix` to `string` unless `string` is empty.'
  return '' if (string == '') else (prefix + string)

def append_to_nonempty(string:str, suffix:str) -> str:
  'append `prefix` to `string` unless `string` is empty.'
  return '' if (string == '') else (string + suffix)


_byte_count_dec_magnitudes = [
  ('B',  'byte'),
  ('kB', 'kilobyte'),
  ('MB', 'megabyte'),
  ('GB', 'gigabyte'),
  ('TB', 'terabyte'),
  ('PB', 'petabyte'),
  ('EB', 'exabyte'),
  ('ZB', 'zettabyte'),
  ('YB', 'yottabyte'),
]

def format_byte_count(count:int, prec=3, abbr=True) -> str:
  "Format a string for the given number of bytes, using the largest appropriate prefix (e.g. 'kB')"
  count = int(count)
  if count < 1000:
    if abbr: return '{:d} B'.format(count)
    else: return pluralize(count, 'byte')
  c = Decimal(count)
  for abbrev, full in _byte_count_dec_magnitudes:
    if c < 999: break
    if c < 1000: # must make sure that c will not round up.
      shift = 10**prec
      if round(c * shift) < 1000 * shift: break
    c /= 1000
  if prec == 0 and not abbr:
    return pluralize(round(c), full)
  # with precision > 0, always pluralize the full names, even if all the digits are zero.
  s = '' if abbr else 's'
  label = abbrev if abbr else full
  return f'{c:.{prec}f} {label}{s}'


def line_col_0(string:str, pos:int) -> Tuple[int, int]:
  if pos < 0 or pos > len(string): raise IndexError(pos)
  line = string.count('\n', 0, pos) # number of newlines preceeding pos.
  last_line_start = string.rfind('\n', 0, pos) + 1 # rfind returns -1 for no match; `+ 1` happens to work perfectly.
  return (line, pos - last_line_start)


def line_col_1(string:str, pos:int) -> Tuple[int, int]:
  l, c = line_col_0(string, pos)
  return (l + 1, c + 1)

