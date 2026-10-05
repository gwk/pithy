# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Adapt detailed Legs Python tokens to Python 3.14 `tokenize` kinds, spelling and code-point positions.

The input is decoded source, encoded as UTF-8 for Legs. Encoding detection belongs to the caller.
The detailed stream contains no token for the adapter's sake. The adapter derives CPython's shapes from it:
* a line break is `NEWLINE` if an `end_of_line` token precedes it, and `NL` otherwise;
* `INDENT` is the leading space that follows an `indent` token;
* a format specification ends at a `field_close` token that has a format mode;
* the line break that CPython adds at the end of an unterminated last line, and `ENDMARKER`, are added here.
Ordinary string fragments are joined here only. Interpolated fragments follow CPython's middle-token boundaries,
including its collapsed doubled braces. TokenInfo.line is the starting physical line, not CPython's internal buffer.
'''

import token as tok
from bisect import bisect_right
from tokenize import TokenInfo
from typing import Iterable, Iterator

from tolkien import Source, Token


_context_keywords_ = ['lexer', 'python', 'tokenize']
_context_status_ = 'experimental'


def python_tokens(source:Source[bytes], tokens:Iterable[Token]) -> Iterator[TokenInfo]:
  'Adapt a detailed stream; compare the first four TokenInfo fields and exact_type with stdlib.'
  positions = _Positions(source.text)
  text_end = len(source.text)
  is_end_of_line = False # An `end_of_line` token precedes the next line break.
  is_indent = False # An `indent` token precedes the next space.
  is_final_line_break_done = False
  ordinary_start:int|None = None
  string_types:list[int] = []
  middle_start:int|None = None
  middle_end = 0
  for token in tokens:
    kind = token.kind
    if kind == 'end_of_line':
      if token.pos == text_end: # The last line has no line break; CPython adds an empty one.
        yield positions.make(tok.NEWLINE, text_end, text_end)
        is_final_line_break_done = True
      else: is_end_of_line = True
      continue
    if kind == 'indent':
      is_indent = True
      continue
    if kind == 'dedent' and token.pos == text_end and not is_final_line_break_done:
      yield from positions.final_line_break()
      is_final_line_break_done = True
    if kind == 'string_start':
      ordinary_start = token.pos
      continue
    if ordinary_start is not None:
      if kind == 'string_end':
        yield positions.make(tok.STRING, ordinary_start, token.end)
        ordinary_start = None
      continue
    is_fragment = token.mode != 'main' and (kind == 'text' or kind.startswith('escape_') or kind == 'backslash')
    if is_fragment or kind in ('brace_escape_o', 'brace_escape_c'):
      if middle_start is None: middle_start = token.pos
      middle_end = token.end
      if kind.startswith('brace_escape_'):
        # CPython ends the middle token after the first of the two braces.
        yield positions.make(string_types[-1], middle_start, middle_end - 1)
        middle_start = None
      continue
    empty_format_prefix = (kind == 'field_open' and token.mode.startswith('fmt')
      and source.text[token.end:token.end + 1] == b'{')
    is_format_end = (kind == 'field_close' and token.mode.startswith('fmt'))
    if middle_start is not None or is_format_end or empty_format_prefix:
      start = token.pos if middle_start is None else middle_start
      end = token.pos if middle_start is None else middle_end
      yield positions.make(string_types[-1], start, end)
      middle_start = None
    if kind in ('fstring_start', 'tstring_start'):
      is_f = kind == 'fstring_start'
      string_types.append(tok.FSTRING_MIDDLE if is_f else tok.TSTRING_MIDDLE)
      yield positions.make(tok.FSTRING_START if is_f else tok.TSTRING_START, token.pos, token.end)
    elif kind in ('fstring_end', 'tstring_end'):
      string_types.pop()
      yield positions.make(tok.FSTRING_END if kind == 'fstring_end' else tok.TSTRING_END, token.pos, token.end)
    elif kind == 'space':
      if is_indent: yield positions.make(tok.INDENT, token.pos, token.end)
      is_indent = False
    elif kind == 'newline':
      yield positions.make(tok.NEWLINE if is_end_of_line else tok.NL, token.pos, token.end)
      is_end_of_line = False
    elif kind != 'continuation':
      token_type = _token_types.get(kind, tok.ERRORTOKEN)
      yield positions.make(token_type, token.pos, token.end)
  if not is_final_line_break_done: yield from positions.final_line_break()
  yield positions.make(tok.ENDMARKER, text_end, text_end)


class _Positions:

  def __init__(self, text:bytes) -> None:
    self.text = text
    self.starts = [0, *(idx + 1 for idx, byte in enumerate(text) if byte == 10)]


  def position(self, pos:int) -> tuple[int,int]:
    idx = bisect_right(self.starts, pos) - 1
    return idx + 1, len(self.text[self.starts[idx]:pos].decode('utf-8'))


  def final_line_break(self) -> Iterator[TokenInfo]:
    'CPython adds an empty `NL` at the end of a last line that has no line break and ends no logical line.'
    if self.text and not self.text.endswith((b'\n', b'\r')): yield self.make(tok.NL, len(self.text), len(self.text))


  def make(self, kind:int, pos:int, end:int) -> TokenInfo:
    start_position = self.position(pos)
    end_position = self.position(end)
    text = self.text[pos:end].decode('utf-8')
    line_start = self.starts[start_position[0] - 1]
    line_end = self.text.find(b'\n', line_start)
    line = self.text[line_start:line_end + 1 if line_end >= 0 else len(self.text)].decode('utf-8')
    if kind in (tok.NEWLINE, tok.NL):
      end_position = (start_position[0], start_position[1] + (len(text) or 1))
    elif kind == tok.ENDMARKER or kind == tok.DEDENT and pos == len(self.text):
      row = len(self.starts) + int(bool(self.text) and not self.text.endswith(b'\n'))
      start_position = end_position = (row, 0)
      line = ''
    return TokenInfo(kind, text, start_position, end_position, line)


_token_types = {
  'name': tok.NAME, 'number': tok.NUMBER, 'op': tok.OP,
  'paren_o': tok.OP, 'paren_c': tok.OP, 'brack_o': tok.OP, 'brack_c': tok.OP, 'brace_o': tok.OP, 'brace_c': tok.OP,
  'field_open': tok.OP, 'field_close': tok.OP, 'format_start': tok.OP,
  'comment': tok.COMMENT, 'dedent': tok.DEDENT,
}
