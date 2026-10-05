# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Detailed Python 3.14 lexing with the modes in `legs_/langs/python/python.legs`.

The generated DFA recognizes fragments; this driver selects modes and handles indentation and replacement fields.
Tokens retain UTF-8 byte offsets and cover the input, including trivia.
String delimiters, text runs and escapes remain separate.
Diagnostics are the job of `py_preprocess.PythonPreprocessor`, which derives them from the stream.

The tokens that cover text keep the kinds of their patterns, apart from the string and field delimiters.
Line structure is conveyed by empty tokens:
* `end_of_line` precedes the line break that ends a logical line, or the end of the text.
  A line break without one is a blank line, a comment line, or within brackets or a replacement field.
* `indent` precedes the leading space of the first line of a deeper block.
* `dedent` precedes the first token of a line that closes a block, or the end of the text.
Indentation is compared as text: a line's leading space must equal an open level or extend the innermost one.
Otherwise the levels that are not prefixes of it are closed and a new level is opened, giving a `dedent` followed by an `indent`.
An abandoned string is marked by an empty `incomplete` token.

`python_tokens` is a separate stdlib compatibility adapter. No token exists solely for its benefit; it derives what it needs.
'''

from typing import Iterator

from tolkien import Source, Token

from ... import DictLexerBase


_context_keywords_ = ['lexer', 'python', 'tokenize']
_context_status_ = 'experimental'


class PythonLexer:
  'A single-use detailed scanner.'

  def __init__(self, source:Source[bytes], lexer_type:type[DictLexerBase]) -> None:
    self.source = source
    self.raw = lexer_type(source)


  def __iter__(self) -> Iterator[Token]:
    yield from self._code()


  def _code(self, field_mode:str='') -> Iterator[Token]:
    brackets:list[Token] = []
    indents = [b''] # The leading space of each open level.
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
          space = self.source.text[whitespace.slc] if whitespace else b''
          if space != indents[-1]:
            count_dedents = 0
            while not space.startswith(indents[-1]):
              indents.pop()
              count_dedents += 1
            if len(space) > len(indents[-1]): # Deeper than the innermost remaining level; this is inconsistent if levels were closed.
              assert whitespace is not None
              indents.append(space)
              for _ in range(count_dedents): yield Token(whitespace.pos, whitespace.pos, kind='dedent')
              yield Token(whitespace.pos, whitespace.pos, kind='indent')
              yield whitespace
              whitespace = None
            else:
              if whitespace:
                yield whitespace
                whitespace = None
              for _ in range(count_dedents): yield Token(token.pos, token.pos, kind='dedent')
        if whitespace:
          yield whitespace
          whitespace = None
        line_start = False
      if kind == 'continuation':
        yield token
        if not logical and not brackets and not field_mode: line_start = True
        continue
      if kind == 'newline':
        if logical and not brackets and not field_mode: yield Token(token.pos, token.pos, kind='end_of_line')
        yield token
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
          yield from self._format(field_mode)
          return
      logical = True
      if kind.endswith('_open'):
        yield from self._string(token)
      elif kind in ('paren_o', 'brack_o', 'brace_o'):
        brackets.append(token)
        yield token
      elif kind in ('paren_c', 'brack_c', 'brace_c'):
        if brackets and brackets[-1].kind[:-1] == kind[:-1]: brackets.pop()
        yield token
      else:
        yield token
    if whitespace: yield whitespace
    if field_mode: return
    if logical: yield Token(self.raw.end, self.raw.end, kind='end_of_line')
    for _ in indents[1:]: yield Token(self.raw.end, self.raw.end, kind='dedent')


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
        self.raw.pos = part.pos # Recover in the enclosing code mode without losing the newline.
        yield Token(part.pos, part.pos, mode=mode, kind='incomplete')
        return
      if formatted and part.kind == 'brace_o':
        yield self._as(part, 'field_open')
        yield from self._code(mode)
      else:
        yield self._fragment(part)
    yield Token(self.raw.end, self.raw.end, mode=mode, kind='incomplete')


  def _format(self, string_mode:str) -> Iterator[Token]:
    family, suffix = string_mode.split('_')
    mode = f'{"fmtr" if family == "fr" else "fmt"}_{suffix}'
    while self.raw.pos < self.raw.end:
      part = self._read(mode)
      if part.kind == 'brace_c':
        yield self._as(part, 'field_close') # The token retains the format mode, which distinguishes the end of a specification.
        return
      if part.kind == 'brace_o':
        yield self._as(part, 'field_open')
        yield from self._code(string_mode)
      elif part.kind == f'quote_{suffix}' or part.kind == 'newline':
        self.raw.pos = part.pos # The enclosing string ends at the quote, or diagnoses and recovers at the newline.
        return
      else:
        yield self._fragment(part)


  def _fragment(self, token:Token) -> Token:
    kind = token.kind
    if kind == 'incomplete' and token.mode.startswith('f') and self.source.text[token.slc] == b'\\':
      if self.source.text[token.end:token.end + 1] in (b'{', b'}'): return self._as(token, 'backslash')
    if kind.endswith('_text') or kind.startswith('quote_'): return self._as(token, 'text')
    return token


  def _read(self, mode:str) -> Token:
    # Python's frames select the DFA mode; the grammar deliberately has no static transitions.
    self.raw.stack[-1] = (mode, None)
    return next(self.raw)


  @staticmethod
  def _as(token:Token, kind:str) -> Token:
    return Token(token.pos, token.end, mode=token.mode, kind=kind)
