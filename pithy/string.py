# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'String utilities.'

import re
from decimal import Decimal
from string import Template
from typing import Any, Callable, cast, Iterable, Iterator, Sequence, TypeVar, Union

from .defaultlist import DefaultList


_T = TypeVar('_T')


class EscapedStr:
  'A `str` wrapper class that signifies (in some external context) that the content has already been properly escaped.'

  def __init__(self, string:str):
    self.string = string

  def __repr__(self) -> str: return f'EscapedStr({self.string!r})'


def render_template(template:str, **substitutions:Any) -> str:
  'Render a template using $ syntax.'
  t = Template(template)
  return t.substitute(substitutions)


def capitalize_first(string:str) -> str:
  '''
  Return `string` with the first character capitalized.
  This differs from `string.capitalize()` in that it does not lowercase the rest of the string.
  '''
  if not string or string[0].isupper(): return string
  return string[0].upper() + string[1:]


def split_camelcase(string:str) -> list[str]:
  'Split a camel-case string (e.g. "camelCase", "CamelCase") into a list of chunks (e.g. ["camel", "Case"]).'
  return [chunk for chunk in re.split(r'([A-Z](?:[a-z]+|[A-Z]*(?=[A-Z]|$)))', string) if chunk]


def typecase_from_snakecase(string:str) -> str:
  'Convert a snake-case string (e.g. "snake_case") to type-case (e.g. "TypeCase").'
  return ''.join(s.capitalize() for s in string.split('_'))


def snakecase_from_camelcase(string:str) -> str:
  'Convert a camel-case string (e.g. "camelCase", "CamelCase") to snake-case (e.g. "snake_case").'
  return '_'.join(s.lower() for s in split_camelcase(string))


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


def clip_common(strings:Sequence[str], prefix=True, suffix=True) -> tuple[str,...]:
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


def replace_first_prefix(string:str, prefixes:Sequence[tuple[str,str]], req=True) -> str:
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


ConvFn = Callable[[Any], str]

def fmt_rows(rows:Iterable[Iterable[Any]], convs:ConvFn|Iterable[ConvFn]=str, rjust:bool|Iterable[bool]=False,
 max_col_width=64) -> Iterable[str]:
  '''
  Format rows of cells to after calculating column widths to justify each cell.
  This function can take any iterable of iterables, but converts all non-sequences to lists/tuples before processing.
  '''
  # Convert all cells to repr or str representations.
  if callable(convs):
    rows = list(tuple(convs(cell) for cell in row) for row in rows)
  else:
    convs = list(convs)
    dflt_conv:ConvFn = cast(ConvFn, convs[-1] if convs else str)
    convs = DefaultList(lambda _: dflt_conv, convs)
    rows = list(tuple(convs[i](cell) for i, cell in enumerate(row)) for row in rows)

  col_widths = DefaultList(lambda _: 0)

  for row in rows: # Get the max width of each column.
    for i, cell in enumerate(row):
      col_widths[i] = max(col_widths[i], len(cell))

  for i, width in enumerate(col_widths): # Clip each column width to max_col_width.
    col_widths[i] = min(width, max_col_width)

  # Determine rjust bool values for each column.
  if isinstance(rjust, bool):
    rjust = [rjust] * len(col_widths)
  else:
    rjust = list(rjust)
    if not rjust: rjust = [False]
    while len(rjust) < len(col_widths): rjust.append(rjust[-1])

  just_fns = [(str.rjust if rj else str.ljust) for rj in rjust]

  for row in rows: # Emit formatted row strings.
    yield '  '.join(just_fn(cell, width) for just_fn, cell, width in zip(just_fns, row, col_widths))



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


def pluralize(count:int, name:str, plural:str|None=None, spec='') -> str:
  '''
  Simple English pluralization for a count/noun pair.
  Return a string of format "{count} {name}s", with optional custom plural form and numerical format spec.
  '''
  if count == 1:
    n = name
  elif plural:
    n = plural
  else:
    n = name + 's'
  return f'{count:{spec}} {n}'


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


def line_col_0(string:str, pos:int) -> tuple[int, int]:
  if pos < 0 or pos > len(string): raise IndexError(pos)
  line = string.count('\n', 0, pos) # number of newlines preceeding pos.
  last_line_start = string.rfind('\n', 0, pos) + 1 # rfind returns -1 for no match; `+ 1` happens to work perfectly.
  return (line, pos - last_line_start)


def line_col_1(string:str, pos:int) -> tuple[int, int]:
  l, c = line_col_0(string, pos)
  return (l + 1, c + 1)


def truncate_str_with_ellipsis(val:Any, max_len:int) -> str:
  s = str(val)
  if len(s) <= max_len: return s
  return s[:max_len-1] + '…'


def truncate_repr_with_ellipsis(val:Any, max_len:int) -> str:
  r = repr(val)
  if len(r) <= max_len: return r
  return r[:max_len-2] + r[0] + '…'


def simplify_punctuation(text:str) -> str:
  text = non_ascii_hyphens_re.sub('-', text) # Replace unicode hyphens.
  text = text.replace('\u2014', '--') # Em dash.
  text = non_ascii_single_quotes.sub("'", text)
  text = non_ascii_double_quotes.sub('"', text)
  return text


StrTree = dict[str,Union['StrTree',None]]

def str_tree(strings:Iterable[str], update:dict[str,dict|None]|None=None, dbg=False) -> StrTree:
  if dbg:
    strings = list(strings)
    print(f'DBG: str_tree: {strings}')
  tree = {} if update is None else update
  for s in strings:
    str_tree_insert(tree, s, dbg=dbg)
  return tree


def str_tree_insert(tree:StrTree, s:str, dbg=False) -> None:
  if dbg: print(f'inserting {s!r} into {tree!r}')
  # Look for a nonempty key prefix, starting with the whole string.
  for lp in range(len(s), 0, -1):
    prefix = s[:lp]
    assert lp == len(prefix) # TEMP
    try: sub = tree[prefix]
    except KeyError: pass # Prefix not found. See below.
    else: # Prefix found.
      if sub is None: # Replace the terminal with a subtree.
        suffix = s[lp:]
        tree[prefix] = { '': None, suffix: None }
      else: # Recurse into the subtree.
        str_tree_insert(sub, s[lp:])
      return
    # Prefix not found. We now also have to check if any other existing key has this prefix.
    for other_k in tree:
      if other_k.startswith(prefix): # Split this key into a subtree.
        other_suffix = other_k[lp:]
        assert prefix + other_suffix == other_k # TEMP
        assert len(other_suffix) > 0 # TEMP
        other = tree.pop(other_k)
        suffix = s[lp:]
        tree[prefix] = {
          suffix: None,
          other_suffix: other }
        return

  # No prefix found, so insert a new terminal.
  assert s not in tree
  tree[s] = None


def str_tree_iter(tree:StrTree, prefix='') -> Iterator[str]:
  for k, sub in tree.items():
    if sub is None: yield prefix + k
    else:
      yield from str_tree_iter(sub, prefix + k)


def str_tree_pairs(tree:StrTree, prefix='') -> Iterator[tuple[str,str]]:
  'Iterate over the tree elements, yielding (shared prefix, unique suffix) pairs.'
  for k, sub in tree.items():
    if sub is None: yield (prefix, k)
    else:
      yield from str_tree_pairs(sub, prefix + k)


non_ascii_single_quotes = re.compile(r'[‘’]')
non_ascii_double_quotes = re.compile(r'[“”]')

non_ascii_hyphens_re = re.compile(r'[\xad\u2010\u2011\u2013\u2212]+')
#^ Soft hyphen, hyphen, non-breaking hyphen, en-dash, minus-sign.

zero_width_space = '\u200b'
