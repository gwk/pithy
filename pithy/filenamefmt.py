# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Parse basic printf style format strings and generate corresponding regular expressions.
This format syntax is intended for use in file names.
'''

import re
from typing import Any, Iterable, Iterator, NamedTuple, Optional, Pattern, Union

from .string import line_col_1


class FilenameFormatterError(Exception): pass


fmt_re = re.compile(r'''(?x)
%
(?P<width>\d*)
(?P<type>[cdosxX%]?)
''')


fmt_type_patterns = {
  'c' : r'.',
  'd' : r'[0-9]',
  'i' : r'[0-9]',
  'o' : r'[0-8]',
  's' : r'.',
  'x' : r'[0-9a-f]',
  'X' : r'[0-9A-F]',
}

single_char_fmts = { 'c', '%' }

fmt_types = {
  'c' : int,
  'd' : int,
  'i' : int,
  'o' : int,
  's' : str,
  'x' : int,
  'X' : int,
}


class FilenameFormatter(NamedTuple):
  min_width: int
  type_char: str
  val_type: type

  def format(self, arg:Any) -> str:
    if self.type_char == 'c':
      assert self.min_width == 0
      return chr(int(arg))
    if self.val_type is int:
      f = ''.join(('{', ':0', str(self.min_width), self.type_char, '}'))
      return f.format(int(arg))
    else:
      assert self.val_type is str
      s = str(arg)
      # TODO: raise if the string contains undesirable characters for file names.
      return s + '_' * (self.min_width - len(s))

  def pattern(self, allow_empty:bool) -> str:
    # TODO: construct this on FilenameFormatter init? May be necessary in format() for more restrictive specifiers, e.g. "w" word, "l" letter.
    pat = fmt_type_patterns[self.type_char]
    if self.type_char in single_char_fmts:
      quant = ''
    elif self.min_width > 0:
      quant = f'{{{self.min_width},}}'
    else:
      quant = '*' if allow_empty else '+'
    return f'({pat}{quant})'


FNFPart = Union[FilenameFormatter,str]


def gen_fnf_parts(fmt: str) -> Iterator[FNFPart]:
  'Generate a sequence of formatter and str objects completely covering the input format string.'

  def _exc(pos: int, msg: str) -> FilenameFormatterError:
    line, col = line_col_1(fmt, pos)
    return FilenameFormatterError(f'<str>:{line}:{col}: {msg}')

  pos = 0
  for match in fmt_re.finditer(fmt):
    start = match.start()
    end = match.end()
    if pos < start:
      yield fmt[pos:start]
    width_str = match.group('width')
    type_char = match.group('type')
    if not type_char:
      end_str = fmt[end] if end < len(fmt) else ''
      raise _exc(end, f'expected type char; received: {end_str!r}')
    if width_str and type_char in single_char_fmts:
      raise  _exc(match.start('width'), f'single-char formatter has disallowed width specifier: {width_str!r}')
    if width_str.startswith('0'):
      raise  _exc(match.start('width'), f'width specifier must not start with zero (zero padding is implied): {width_str!r}')
    if type_char == '%':
      yield '%'
    else:
      min_width = int(width_str) if width_str else 0 # Should not fail thanks to regex.
      val_type = fmt_types[type_char]
      yield FilenameFormatter(min_width=min_width, type_char=type_char, val_type=val_type)
    pos = end
  if pos != len(fmt):
    yield fmt[pos:len(fmt)]


def fnf_parts_have_formatter(parts: Iterable[FNFPart]) -> bool:
  'Returns True if `string` contains a format pattern.'
  for part in parts:
    if isinstance(part, FilenameFormatter):
      return True
  return False


def fnf_str_has_formatter(string: str) -> bool: return fnf_parts_have_formatter(gen_fnf_parts(string))


def count_fnf_parts_formatters(parts:Iterable[FNFPart]) -> int:
  count = 0
  for part in parts:
    if isinstance(part, FilenameFormatter):
      count += 1
  return count


def count_fnf_str_formatters(string: str) -> int: return count_fnf_parts_formatters(gen_fnf_parts(string))


def format_fnf_parts(parts:Iterable[FNFPart], args:Iterable[Any]) -> str:
  parts = tuple(parts)
  args = tuple(args)
  num_formatters = count_fnf_parts_formatters(parts)
  if num_formatters != len(args):
    raise ValueError(f'unequal number of formatters ({num_formatters}) and arguments ({len(args)})')
  res:list[str] = []
  args_it = iter(args)
  for part in parts:
    if isinstance(part, str):
      res.append(part)
    else:
      res.append(part.format(next(args_it)))
  return ''.join(res)


def format_fnf_str(string:str, args:Iterable[Any]) -> str:
  return format_fnf_parts(gen_fnf_parts(string), args)


def regex_for_fnf_parts(parts:Iterable[FNFPart], allow_empty:bool) -> Pattern[str]:
  'Translate formatter parts into a regular expression pattern.'
  return re.compile(''.join((re.escape(part) if isinstance(part, str) else part.pattern(allow_empty)) for part in parts))


def regex_for_fnf_str(string:str, allow_empty:bool) -> Pattern[str]:
  return regex_for_fnf_parts(gen_fnf_parts(string), allow_empty=allow_empty)
