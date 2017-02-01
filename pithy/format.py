# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Simple lexing.'

import re
from .string_utils import line_col_1
from typing import AnyStr, Iterable, re as Re

class FormatError(Exception): pass

fmt_re = re.compile(r'''(?x:
\{
  ((?: # capture group 1 is the entire format contents.
    [^{}]
    | (?: \{ [^{}]* \} ) # allow a single level of nested formatters;
  )*)
\}
| \{\{
| \}\}
| [^{}]+
)''')

# translated from "6.1.3.1. Format Specification Mini-Language".
fmt_spec_re = re.compile(r'''(?x:
(?: (?P<fill> . )? (?P<align> [<>=^]) )?
(?P<sign> [-+\ ] )?
(?P<alt> \# )?
(?P<zero> 0 ) ?
(?P<width> \d+ | \{ [^{}]* \} )? # note: nested format.
(?P<grouping> [_,] )?
(?: \. (?P<precision> \d+ | \{ [^{}]* \} ) )? # note: nested format.
(?P<type> [bcdeEfFgGnosxX%] )?
)''')

fmt_spec_dynamic_re = re.compile(r':[^}]\{')

spec_type_pat = {
  'd': r'\d'
}


def format_to_re(fmt: str, error_prefix='error', path='<str>') -> str:
  'translate a format string into a regular expression pattern.'
  pos = 0
  chunks = []

  def exc(msg=None):
    prefix = error_prefix + ' ' if error_prefix else ''
    line, col = line_col_1(fmt, pos)
    if not msg:
      c = fmt[pos]
      msg = f'invalid format character: {c!r}'
    return FormatError(f'{error_prefix}: {path}:{line}:{col}: {msg}')

  for match in fmt_re.finditer(fmt):
    if match.start() != pos: raise exc()
    pos = match.end()
    text = match.group()
    fmt_text = match.group(1)
    if fmt_text is not None: # this chunk is a format.
      colon_pos = fmt_text.find(':')
      if colon_pos == -1: # no format spec.
        pat = '.*'
      else:
        spec_text = fmt_text[colon_pos + 1:]
        spec_match = fmt_spec_re.fullmatch(spec_text)
        if not spec_match: raise exc(f'invalid format spec: {spec_text!r}')
        fill, align, sign, alt, zero, width, grouping, precision, type_ = spec_match.group(
          'fill', 'align', 'sign', 'alt', 'zero', 'width', 'grouping', 'precision', 'type')
        if type_:
          try: pat = spec_type_pat[type_] + '+'
          except KeyError as e: raise exc(f'spec type {type_!r} not implemented')
        else:
          pat = '.*'
      pattern = '(' + pat + ')'
    elif text == '{{': pattern = '\{'
    elif text == '}}': pattern = '\}'
    else: pattern = re.escape(text)
    chunks.append(pattern)
  if pos != len(fmt): raise exc()
  return re.compile(''.join(chunks))
