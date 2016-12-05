# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from decimal import Decimal
from string import Template
from typing import Any, Iterable, Iterator, Sequence, TypeVar

T = TypeVar('T')


def render_template(template: str, **substitutions: Any) -> str:
  'Render a template using $ syntax.'
  t = Template(template)
  return t.substitute(substitutions)


def string_contains(string: str, query: str) -> bool:
  'Return True if string contains query.'
  return string.find(query) != -1


def clip_prefix(string: str, prefix: str, req=True) -> str:
  'Remove `prefix` if it is present, or raise ValueError, unless `req` is False.'
  if string.startswith(prefix):
    return string[len(prefix):]
  elif req:
    raise ValueError(string)
  return string


def  clip_suffix(string: str, suffix: str, req=True) -> str:
  'Remove `suffix`if it is present, or raise ValueError, unless `req` is False.'
  if len(suffix) == 0: return string # need this case because string[:-0] == ''.
  if string.endswith(suffix):
    return string[:-len(suffix)]
  elif req:
    raise ValueError(string)
  return string


def clip_first_prefix(string: str, prefixes: Sequence[str], req=True) -> str:
  'Remove the first matching prefix in `prefixes` from `string`, or raise ValueError, unless `req is False`.'
  for p in prefixes:
    try:
      return clip_prefix(string, p, req=True)
    except ValueError:
      continue
  if req:
    raise ValueError(string)
  return string


def iter_excluding_str(iterable: Iterable[T]) -> Iterator[T]:
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


def pluralize(count: int, name: str, plural=None, spec='') -> str:
  'Return a string of format "{count} {name}s", with optional custom plural form and format spec.'
  if count == 1:
    n = name
  elif plural is None:
    n = name + 's'
  else:
    n = plural
  return '{count:{spec}} {n}'.format(count=count, spec=spec, n=n)


def format_nonempty(fmt: str, string: str) -> str:
  'format `string` into `format` unless `string` is empty.'
  return '' if (string == '') else fmt.format(string)

def prefix_nonempty(prefix: str, string: str) -> str:
  'prepend `prefix` to `string` unless `string` is empty.'
  return '' if (string == '') else (prefix + string)


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

def format_byte_count(count: int, prec=3, abbr=True) -> str:
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
  return '{c:.{prec}f} {label}{s}'.format(c=c, prec=prec, label=label, s=s)

