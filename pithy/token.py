# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Immutable Token class.
'''

from typing import NoReturn, Optional, Tuple

_setattr = object.__setattr__

Slice = slice

class Token:
  __slots__ = ('source', 'pos', 'end', 'kind')
  source:str
  pos:int
  end:int
  kind:str

  def __init__(self, source:str, pos:int, end:int, kind:str) -> None:
    _setattr(self, 'source', source)
    _setattr(self, 'pos', pos)
    _setattr(self, 'end', end)
    _setattr(self, 'kind', kind)

  def __str__(self) -> str:
    return f'{self.pos}-{self.end}:{self.kind!r}'

  def __repr__(self) -> str:
    return f'{type(self).__qualname__}(pos={self.pos}, end={self.end}, kind={self.kind!r})'

  @property
  def slice(self) -> Slice:
    return slice(self.pos, self.end)

  @property
  def text(self) -> str:
    return self.source[self.pos:self.end]

  def pos_token(self) -> 'Token':
    'Create a new token with the same position as `token` but with zero length.'
    return Token(source=self.source, pos=self.pos, end=self.pos, kind=self.kind)

  def fail(self, path:str, msg:str) -> NoReturn:
    'Print a formatted parsing failure to std err and exit.'
    exit(self.diagnostic(prefix=path, msg=msg))


  def diagnostic(self, prefix:str, msg:str, pos:Optional[int]=None, end:Optional[int]=None) -> str:
    'Return a formatted parser error message.'
    if pos is None: pos = self.pos
    else: assert pos >= self.pos
    if end is None: end = self.end
    else: assert end <= self.end
    line_num = self.source.count('\n', 0, pos) # number of newlines preceeding pos.
    line_start = self.source.rfind('\n', 0, pos) + 1 # rfind returns -1 for no match, happens to work perfectly.
    line_end = self.source.find('\n', pos)
    if line_end == -1: line_end = len(self.source)
    line = self.source[line_start:line_end]
    col = pos - line_start
    indent = ''.join('\t' if c == '\t' else ' ' for c in line[:col])
    src_bar = '| ' if line else '|'
    underline = '~' * (min(end - pos, len(line))) or '^'
    return f'{prefix}:{line_num+1}:{col+1}: {msg}\n{src_bar}{line}\n  {indent}{underline}'


  def line_col_0(self, source:str) -> Tuple[int,int]:
    'Return a pair of 0-indexed line and column numbers for the token.'
    pos = self.pos
    line_num = source.count('\n', 0, self.pos) # number of newlines preceeding pos.
    line_start = source.rfind('\n', 0, self.pos) + 1 # rfind returns -1 for no match, happens to work perfectly.
    return (line_num, pos - line_start)

