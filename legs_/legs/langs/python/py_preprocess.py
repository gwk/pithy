# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Diagnostics for the detailed Python token stream.

`PythonPreprocessor` has the `pithy.parse.Preprocessor` signature: it takes the source and the tokens of `PythonLexer`,
yields the tokens unchanged, and accumulates `LexIssue` records.
It derives every diagnostic from the stream alone: the kinds and modes of the tokens, their text, and the empty tokens
that mark abandoned strings and line structure. It does not depend on tokens that a parser drops, such as spaces.
'''

from dataclasses import dataclass
from typing import Iterable, Iterator
from unicodedata import lookup

from tolkien import Source, Token


_context_keywords_ = ['diagnostics', 'lexer', 'preprocessor', 'python']
_context_status_ = 'experimental'


@dataclass(frozen=True)
class LexIssue:
  'An error at a byte span, with the opening delimiter retained when applicable.'
  kind:str
  pos:int
  end:int
  message:str
  opening:int|None = None


@dataclass(frozen=True)
class _Frame:
  'An open construct: a string, a replacement field, a format specification or a bracket.'
  kind:str # 'string', 'field', 'format' or 'bracket'.
  pos:int # The position of the opening token.
  close_kind:str = '' # For brackets, the kind of the closing token.
  is_bytes:bool = False # For strings, whether the literal is bytes.


class PythonPreprocessor:
  'Yields the tokens of a detailed stream unchanged and records the issues that it finds. Instances are single-use.'

  def __init__(self) -> None:
    self.issues:list[LexIssue] = []


  def __call__(self, source:Source[bytes], tokens:Iterable[Token]) -> Iterator[Token]:
    text = source.text
    text_end = len(text)
    frames:list[_Frame] = []
    was_dedent = False
    last:Token|None = None
    for token in tokens:
      kind = token.kind
      mode = token.mode
      string_frame = next((f for f in reversed(frames) if f.kind == 'string'), None)
      field_frame = next((f for f in reversed(frames) if f.kind == 'field'), None)
      if mode.startswith('fmt'): opening = field_frame.pos if field_frame else None
      elif mode != 'main': opening = string_frame.pos if string_frame else None
      else: opening = field_frame.pos if field_frame else None
      if kind == 'indent' and was_dedent: # The indentation is not an open level, so the lexer closed levels and opened a new one.
        end = token.pos
        while end < text_end and text[end] in b' \t\x0c': end += 1
        self.issues.append(LexIssue('invalid', token.pos, end, 'Inconsistent indentation.'))
      was_dedent = (kind == 'dedent')
      if kind in ('string_start', 'fstring_start', 'tstring_start'):
        prefix = text[token.slc].lower()
        frames.append(_Frame('string', token.pos, is_bytes=(b'b' in prefix)))
      elif kind in ('string_end', 'fstring_end', 'tstring_end'):
        if frames and frames[-1].kind in ('field', 'format'): # The quote ended a format specification; the lexer reread it.
          self.issues.append(LexIssue('invalid', token.pos, token.end, 'Expected a closing replacement-field brace.',
            field_frame.pos if field_frame else None))
        self._pop_through(frames, 'string')
      elif kind == 'field_open': frames.append(_Frame('field', token.pos))
      elif kind == 'format_start': frames.append(_Frame('format', opening or token.pos))
      elif kind == 'field_close': self._pop_through(frames, 'field')
      elif mode == 'main':
        if kind in ('paren_o', 'brack_o', 'brace_o'): frames.append(_Frame('bracket', token.pos, close_kind=kind[:-1] + 'c'))
        elif kind in ('paren_c', 'brack_c', 'brace_c'):
          if frames and frames[-1].kind == 'bracket' and frames[-1].close_kind == kind: frames.pop()
          else: self.issues.append(LexIssue('invalid', token.pos, token.end, 'Unmatched closing delimiter.'))
        elif kind == 'name': self._check_name(text, token)
        elif kind == 'invalid': self.issues.append(LexIssue('invalid', token.pos, token.end, 'Invalid Python token.'))
        elif kind == 'incomplete': self._incomplete(text, token, opening)
      else: # A string fragment, or a marker within a string.
        data = text[token.slc]
        if kind == 'incomplete':
          if token.pos == token.end: # The string was abandoned at a line break, or at the end of the text.
            if token.pos < text_end:
              end = token.pos + (2 if text.startswith(b'\r\n', token.pos) else 1)
              self.issues.append(LexIssue('invalid', token.pos, end, 'Unescaped newline in a single-quoted string.', opening))
              self._pop_through(frames, 'string')
          else: self._incomplete(text, token, opening)
        elif kind == 'invalid': self.issues.append(LexIssue('invalid', token.pos, token.end, 'Invalid string fragment.', opening))
        elif kind == 'brace_c' and mode.startswith('f'):
          self.issues.append(LexIssue('invalid', token.pos, token.end, 'A literal closing brace must be doubled.', opening))
        elif kind == 'escape_named':
          try: lookup(data[3:-1].decode('ascii'))
          except KeyError: self.issues.append(LexIssue('invalid', token.pos, token.end, 'Unknown Unicode character name.', opening))
        elif kind == 'escape_U' and int(data[2:], 16) > 0x10ffff:
          self.issues.append(LexIssue('invalid', token.pos, token.end, 'Unicode escape is out of range.', opening))
        if string_frame and string_frame.is_bytes and kind not in ('invalid', 'incomplete') and not data.isascii():
          pos = token.pos
          for char in data.decode('utf-8'):
            end = pos + len(char.encode('utf-8'))
            if ord(char) > 127:
              self.issues.append(LexIssue('invalid', pos, end, 'Non-ASCII character in a bytes literal.', opening))
            pos = end
      last = token
      yield token
    if last is not None and last.kind == 'continuation':
      self.issues.append(LexIssue('incomplete', text_end, text_end, 'Expected a continued line.', last.pos))
    for idx in range(len(frames) - 1, -1, -1): # Report the unclosed constructs, innermost first.
      frame = frames[idx]
      match frame.kind:
        case 'bracket': message = 'Unclosed delimiter.'
        case 'field': message = 'Unclosed replacement field.'
        case 'format': message = 'Unclosed format specification.'
        case _: message = 'Unclosed string.'
      if frame.kind == 'field' and idx + 1 < len(frames) and frames[idx + 1].kind == 'format': continue # The specification was reported.
      self.issues.append(LexIssue('incomplete', text_end, text_end, message, frame.pos))


  @staticmethod
  def _pop_through(frames:list[_Frame], kind:str) -> None:
    'Pop frames up to and including the innermost frame of `kind`.'
    while frames:
      if frames.pop().kind == kind: return


  def _check_name(self, text:bytes, token:Token) -> None:
    name = text[token.slc].decode('utf-8')
    if name.isidentifier(): return
    pos = token.pos
    for idx, char in enumerate(name):
      end = pos + len(char.encode('utf-8'))
      if not (char.isidentifier() if idx == 0 else ('a' + char).isidentifier()):
        self.issues.append(LexIssue('invalid', pos, end, 'Invalid identifier character.'))
      pos = end


  def _incomplete(self, text:bytes, token:Token, opening:int|None) -> None:
    'A nonempty `incomplete` token: the text ended, or the next character could not continue the token.'
    if token.end == len(text):
      self.issues.append(LexIssue('incomplete', token.end, token.end, 'Incomplete token.', opening))
    else:
      end = token.end + 1
      while end < len(text) and text[end] & 0xc0 == 0x80: end += 1
      self.issues.append(LexIssue('invalid', token.end, end, 'Unexpected character after an incomplete token.', opening))
