# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Simple lexing.'

import re
from .string_utils import line_col_1
from typing import AnyStr, Iterable, re as Re

class FormatError(Exception): pass

fmt_re = re.compile(r'''(?x:
\{
  (?:
    [^{}]
    | (?: \{ [^}]* \} ) # allow a single level of nested formatters.
  )*
\}
| \{\{
| \}\}
| [^{}]+
)''')


def format_to_re(fmt: str, error_prefix='error', path='<str>') -> str:
  'translate a format string into a regular expression pattern.'
  pos = 0
  chunks = []

  def exc():
    prefix = error_prefix + ' ' if error_prefix else ''
    line, col = line_col_1(fmt, pos)
    c = fmt[pos]
    return FormatError(f'{error_prefix}: {path}:{line}:{col}: invalid format character: {c!r}')

  for match in fmt_re.finditer(fmt):
    if match.start() != pos: raise exc()
    pos = match.end()
    text = match.group()
    if text[0] == '{' and text[-1] == '}': # format.
      pattern = '(.*)' # get get much fancier but this will suffice for now.
    elif text == '{{': pattern = '\{'
    elif text == '}}': pattern = '\}'
    else: pattern = re.escape(text)
    chunks.append(pattern)
  if pos != len(fmt): raise exc()
  return re.compile(''.join(chunks))
