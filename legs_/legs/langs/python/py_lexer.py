# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Detailed Python 3.14 lexing with the modes in `legs_/langs/python/python.legs`.

The generated DFA recognizes fragments; this coordinator selects modes and handles indentation and replacement fields.
Tokens retain UTF-8 byte offsets and cover the input, including trivia. Structural tokens can have empty spans.
String delimiters, text runs and escapes remain separate. `python_tokens` is a separate stdlib compatibility adapter.
Build the grammar once and pass the resulting lexer class to each scanner. No stdlib tokenizer is used for recognition.
'''

from dataclasses import dataclass
from typing import Iterator
from unicodedata import lookup

from tolkien import Source, Token

from ... import DictLexerBase


_context_keywords_ = ['lexer', 'python', 'tokenize']
_context_status_ = 'experimental'


@dataclass(frozen=True)
class LexIssue:
  'An error at a byte span, with the opening delimiter retained when applicable.'
  kind:str
  pos:int
  end:int
  message:str
  opening:int|None = None


class PythonLexer:
  'A single-use detailed scanner. Issues accumulate as its token iterator is consumed.'

  def __init__(self, source:Source[bytes], lexer_type:type[DictLexerBase]) -> None:
    self.source = source
    self.raw = lexer_type(source)
    self.issues:list[LexIssue] = []


  def __iter__(self) -> Iterator[Token]:
    yield from self._code()


  def _code(self, field_mode:str='', opening:int|None=None) -> Iterator[Token]:
    brackets:list[Token] = []
    indents = [0]
    line_start = not field_mode
    logical = False
    whitespace:Token|None = None
    while self.raw.pos < self.raw.end:
      token = self._read('main')
      kind = token.kind
      text = self.source.text[token.slc]
      if kind == 'space' and line_start:
        whitespace = token
        continue
      if line_start:
        if kind not in ('comment', 'newline', 'continuation'):
          width = 0
          if whitespace:
            for byte in self.source.text[whitespace.slc]:
              width = (width // 8 + 1) * 8 if byte == 9 else 0 if byte == 12 else width + 1
          if width > indents[-1]:
            indents.append(width)
            if whitespace:
              yield self._as(whitespace, 'indent')
              whitespace = None
          else:
            if whitespace:
              yield whitespace
              whitespace = None
            while width < indents[-1]:
              indents.pop()
              yield Token(token.pos, token.pos, kind='dedent')
            if width != indents[-1]: self._issue(token, 'invalid', 'Inconsistent indentation.')
        if whitespace:
          yield whitespace
          whitespace = None
        line_start = False
      if kind == 'continuation':
        yield token
        if not logical and not brackets and not field_mode: line_start = True
        if self.raw.pos == self.raw.end: self._eof('Expected a continued line.', token.pos)
        continue
      if kind == 'newline':
        yield self._as(token, 'nl' if brackets or field_mode or not logical else 'newline')
        if not brackets and not field_mode:
          logical = False
          line_start = True
        continue
      if kind in ('space', 'comment'):
        yield token
        continue
      if field_mode and not brackets:
        if kind == 'brace_c':
          yield self._as(token, 'field_close')
          return
        if text.startswith(b':'):
          # At field depth zero, even ':=' starts a format specification. A walrus needs parentheses.
          self.raw.pos = token.pos + 1
          token = Token(token.pos, self.raw.pos, kind='op')
          yield self._as(token, 'format_start')
          yield from self._format(field_mode, opening)
          return
      logical = True
      if kind.endswith('_open'):
        yield from self._string(token)
      elif kind in ('paren_o', 'brack_o', 'brace_o'):
        brackets.append(token)
        yield token
      elif kind in ('paren_c', 'brack_c', 'brace_c'):
        if not brackets or brackets[-1].kind[:-1] != kind[:-1]:
          self._issue(token, 'invalid', 'Unmatched closing delimiter.')
        else:
          brackets.pop()
        yield token
      elif kind == 'name':
        name = text.decode('utf-8')
        if not name.isidentifier():
          pos = token.pos
          for idx, char in enumerate(name):
            end = pos + len(char.encode('utf-8'))
            if not (char.isidentifier() if idx == 0 else ('a' + char).isidentifier()):
              self.issues.append(LexIssue('invalid', pos, end, 'Invalid identifier character.'))
            pos = end
        yield token
      else:
        if kind == 'incomplete': self._incomplete(token, opening)
        elif kind == 'invalid': self._issue(token, kind, 'Invalid Python token.')
        yield token
    if whitespace: yield whitespace
    for bracket in brackets:
      self._eof('Unclosed delimiter.', bracket.pos)
    if field_mode:
      self._eof('Unclosed replacement field.', opening)
      return
    if logical:
      yield Token(self.raw.end, self.raw.end, kind='newline')
    elif self.raw.end and self.source.text[-1:] not in (b'\n', b'\r'):
      yield Token(self.raw.end, self.raw.end, kind='nl')
    for _ in indents[1:]: yield Token(self.raw.end, self.raw.end, kind='dedent')
    yield Token(self.raw.end, self.raw.end, kind='endmarker')


  def _string(self, token:Token) -> Iterator[Token]:
    family, suffix, _ = token.kind.split('_')
    formatted = family in ('f', 'fr', 't', 'tr')
    mode_family = {'t': 'f', 'tr': 'fr', 'rawbytes': 'raw'}.get(family, family)
    mode = f'{mode_family}_{suffix}'
    string_kind = ('tstring' if family in ('t', 'tr') else 'fstring') if formatted else 'string'
    yield self._as(token, string_kind + '_start')
    while self.raw.pos < self.raw.end:
      part = self._read(mode)
      if part.kind == f'quote_{suffix}':
        yield self._as(part, string_kind + '_end')
        return
      if part.kind == 'newline':
        self._issue(part, 'invalid', 'Unescaped newline in a single-quoted string.', token.pos)
        self.raw.pos = part.pos # Recover in the enclosing code mode without losing the newline.
        yield Token(part.pos, part.pos, mode=mode, kind='incomplete')
        return
      if formatted and part.kind == 'brace_o':
        yield self._as(part, 'field_open')
        yield from self._code(mode, part.pos)
      else:
        if formatted and part.kind == 'brace_c':
          self._issue(part, 'invalid', 'A literal closing brace must be doubled.', token.pos)
        yield from self._fragment(part, family in ('bytes', 'rawbytes'), token.pos)
    self._eof('Unclosed string.', token.pos)
    yield Token(self.raw.end, self.raw.end, mode=mode, kind='incomplete')


  def _format(self, string_mode:str, opening:int|None) -> Iterator[Token]:
    family, suffix = string_mode.split('_')
    mode = f'{"fmtr" if family == "fr" else "fmt"}_{suffix}'
    while self.raw.pos < self.raw.end:
      part = self._read(mode)
      if part.kind == 'brace_c':
        yield Token(part.pos, part.pos, mode=mode, kind='format_end')
        yield self._as(part, 'field_close')
        return
      if part.kind == 'brace_o':
        yield self._as(part, 'field_open')
        yield from self._code(string_mode, part.pos)
      elif part.kind == f'quote_{suffix}':
        self._issue(part, 'invalid', 'Expected a closing replacement-field brace.', opening)
        self.raw.pos = part.pos
        return
      elif part.kind == 'newline':
        self.raw.pos = part.pos # The enclosing single-quoted string diagnoses and recovers at this newline.
        return
      else:
        yield from self._fragment(part, False, opening)
    self._eof('Unclosed format specification.', opening)


  def _fragment(self, token:Token, is_bytes:bool, opening:int|None) -> Iterator[Token]:
    kind = token.kind
    data = self.source.text[token.slc]
    if kind == 'incomplete' and data == b'\\' and token.mode.startswith('f'):
      if self.source.text[token.end:token.end + 1] in (b'{', b'}'):
        yield self._as(token, 'backslash')
        return
    if kind == 'incomplete': self._incomplete(token, opening)
    elif kind == 'invalid': self._issue(token, kind, 'Invalid string fragment.', opening)
    elif kind == 'escape_named':
      try: lookup(data[3:-1].decode('ascii'))
      except KeyError: self._issue(token, 'invalid', 'Unknown Unicode character name.', opening)
    elif kind == 'escape_U' and int(data[2:], 16) > 0x10ffff:
      self._issue(token, 'invalid', 'Unicode escape is out of range.', opening)
    if is_bytes and kind not in ('invalid', 'incomplete') and not data.isascii():
      pos = token.pos
      for char in data.decode('utf-8'):
        end = pos + len(char.encode('utf-8'))
        if ord(char) > 127:
          self.issues.append(LexIssue('invalid', pos, end, 'Non-ASCII character in a bytes literal.', opening))
        pos = end
    if kind.endswith('_text') or kind.startswith('quote_'): token = self._as(token, 'text')
    yield token


  def _read(self, mode:str) -> Token:
    # Python's frames select the DFA mode; the grammar deliberately has no static transitions.
    self.raw.stack[-1] = (mode, None)
    return next(self.raw)


  def _issue(self, token:Token, kind:str, message:str, opening:int|None=None) -> None:
    self.issues.append(LexIssue(kind, token.pos, token.end, message, opening))


  def _eof(self, message:str, opening:int|None) -> None:
    self.issues.append(LexIssue('incomplete', self.raw.end, self.raw.end, message, opening))


  def _incomplete(self, token:Token, opening:int|None) -> None:
    if token.end == self.raw.end:
      self._eof('Incomplete token.', opening)
    else:
      end = token.end + 1
      while end < self.raw.end and self.source.text[end] & 0xc0 == 0x80: end += 1
      self.issues.append(LexIssue('invalid', token.end, end, 'Unexpected character after an incomplete token.', opening))


  @staticmethod
  def _as(token:Token, kind:str) -> Token:
    return Token(token.pos, token.end, mode=token.mode, kind=kind)
