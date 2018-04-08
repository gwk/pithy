# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Iterable, Iterator, List, Tuple
from pithy.dataclasses import dataclass


@dataclass(frozen=True)
class Syntax:

  @dataclass(frozen=True)
  class Pos:
    '''
    All indices are zero-based.
    '''
    line: int
    col: int
    end_line: int
    end_col: int

    def __init__(self, *, line=-1, col=-1, end_line=-1, end_col=-1, enclosed:Iterable['Pos']=()) -> 'Pos':
      for pos in enclosed:
        if pos.line >= 0:
          if line < 0 or line > pos.line: line = pos.line
          if pos.col >= 0 and line == pos.line and (col < 0 or col > pos.col): col = pos.col
          if pos.end_line >= 0:
            if end_line < pos.end_line: end_line = pos.end_line
            if pos.end_col >= 0 and end_line == pos.end_line and end_col < pos.end_col: end_col = pos.end_col
      set_ = super().__setattr__
      set_('line', line)
      set_('col', col)
      set_('end_line', end_line)
      set_('end_col', end_col)

    @property
    def path(self) -> str:
      '''
      'VSCode does not recognize paths unless they contain a slash,
      so add a leading `./` to any name that does not look special.
      '''
      return self.name if ('<' in self.name or '/' in self.name) else './' + self.name

    def __str__(self): return f'{self.line+1:04}:{self.col+1:03}'

    def expand(self, pos:'Pos') -> 'Pos':
      line = self.line
      col = self.col
      end_line = self.end_line
      end_col = self.end_col
      if line < 0 or line > pos.line: line = pos.line
      if line == pos.line and (col < 0 or col > pos.col): col = pos.col
      if end_line < pos.end_line: end_line = pos.end_line
      if end_line == pos.end_line and end_col < pos.end_col: end_col = pos.end_col
      return Pos(line=line, col=col, end_line=end_line, end_col=end_col)


  path: str
  pos: Pos
  kind: str
  text: str
  children: Tuple['Syntax', ...]


  def describe(self, *, prefix='', depth=0) -> Iterator[str]:
    spaces = '  ' * depth
    kind = f' {self.kind}:' if self.kind else ''
    if self.text:
      text = f' {self.text!r}' if len(self.text) <= 64 else f' {self.text[:64]!r}…'
    else:
      text = ''
    yield f'{prefix}{self.path}:{self.pos}:{spaces}{kind}{text}'
    for child in self.children:
      yield from child.describe(prefix=prefix, depth=depth+1)
