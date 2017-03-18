# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Simple lexing.'

import re
from .string_utils import line_col_1
from typing import Any, AnyStr, Iterable, re as Re

class FormatError(Exception): pass

fmt_re = re.compile(r'''(?x)
(?P<formatter>\{
        (?P<name> [^{}!:]* )
  (?: ! (?P<conv> [ars] ) )?
  (?: : (?P<spec> (?: [^{}] | \{ [^{}]* \} )* ) )?
  #^ for the spec, we allow a single level of nested formatters.
\})
| \{\{
| \}\}
| [^{}]+
''')

# translated from "6.1.3.1. Format Specification Mini-Language".
fmt_spec_re = re.compile(r'''(?x)
(?: (?P<fill> . )? (?P<align> [<>=^]) )?
(?P<sign> [-+\ ] )?
(?P<alt> \# )?
(?P<zero> 0 ) ?
(?P<width> \d+ | \{ [^{}]* \} )? # note: nested format.
(?P<grouping> [_,] )?
(?: \. (?P<precision> \d+ | \{ [^{}]* \} ) )? # note: nested format.
(?P<type> [bcdeEfFgGnosxX%] )?
''')

fmt_spec_dynamic_re = re.compile(r':[^}]\{')

spec_type_pats = {
  'd': r'\d'
}

spec_types = {
  'd': int
}


def has_formatter(string: str) -> bool:
  'Returns True if `string` contains a format pattern.'
  for match in gen_format_matches(string):
    if match.group('formatter'):
      return True
  return False


def count_formatters(fmt: str) -> int:
  count = 0
  for match in gen_format_matches(fmt):
    if match.group('formatter'):
      count += 1
  return count


def parse_formatters(fmt: str) -> Iterable[Re.Match]:
  for match in gen_format_matches(fmt):
    formatter = match.group('formatter')
    if formatter is not None:
      value_type = str
      name, conv, spec = match.group('name', 'conv', 'spec')
      if spec:
        spec_match = fmt_spec_re.fullmatch(spec)
        if not spec_match: raise exc(match, f'invalid format spec: {spec!r}')
        fill, align, sign, alt, zero, width, grouping, precision, type_ = spec_match.group(
          'fill', 'align', 'sign', 'alt', 'zero', 'width', 'grouping', 'precision', 'type')
        if type_:
          try: value_type = spec_types[type_]
          except KeyError as e: raise exc(match, f'spec type {type_!r} not implemented') from e
      yield (name, conv, spec, value_type)


def format_partial(fmt: str, *args: str, **kwargs: Any) -> str:
  args_it = iter(args)
  def format_frag(match):
    formatter = match.group('formatter')
    if formatter:
      name = match.group('name')
      if name:
        try: return formatter.format(**kwargs)
        except KeyError: return formatter
      else:
        try: return formatter.format(next(args_it), **kwargs)
        except (StopIteration, KeyError): return formatter
    return match.group()
  return ''.join(format_frag(m) for m in gen_format_matches(fmt))


def format_to_re(fmt: str) -> str:
  'translate a format string into a regular expression pattern.'
  def pattern_from(match: Re.Match) -> Iterable[str]:
    def exc(msg): return _exc(fmt, match.start(), msg)
    if match.group('formatter'):
      spec = match.group('spec')
      if not spec:
        pat = '.*'
      else:
        spec_match = fmt_spec_re.fullmatch(spec)
        if not spec_match: raise exc(match, f'invalid format spec: {spec!r}')
        fill, align, sign, alt, zero, width, grouping, precision, type_ = spec_match.group(
          'fill', 'align', 'sign', 'alt', 'zero', 'width', 'grouping', 'precision', 'type')
        if type_:
          try: pat = spec_type_pats[type_] + '+'
          except KeyError as e: raise exc(match, f'spec type {type_!r} not implemented') from e
        else:
          pat = '.*'
      name = match.group('name')
      if name: return f'(?P<{name}>{pat})'
      else: return f'({pat})'
    text = match.group()
    if text == '{{': return '\{'
    if text == '}}': return '\}'
    return re.escape(text)
  return re.compile(''.join(pattern_from(m) for m in gen_format_matches(fmt)))


def gen_format_matches(fmt: str) -> Iterable[str]:
  pos = 0
  def exc(): return _exc(fmt, pos, f'invalid format character: {fmt[pos]!r}')
  for match in fmt_re.finditer(fmt):
    if match.start() != pos: raise exc()
    pos = match.end()
    yield match
  if pos != len(fmt): raise exc()


def _exc(fmt, pos, msg):
  line, col = line_col_1(fmt, pos)
  return FormatError(f'<str>:{line}:{col}: {msg}')

