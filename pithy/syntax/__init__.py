# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any, Callable, Generic, Iterable, Iterator, List, Tuple, TypeVar
from pithy.dataclasses import dataclass


SyntaxStack = Tuple['Syntax', ...]


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

    def __init__(self, *, line=-1, col=-1, end_line=-1, end_col=-1, enclosed:Iterable[Any]=()) -> None:
      for el in enclosed:
        if el is None: continue
        pos = el if isinstance(el, Syntax.Pos) else el.pos # `enclosed` elements should either be a `Pos` or have a `pos`.
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

    def __str__(self): return f'{self.line+1:04}:{self.col+1:03}-{self.end_line+1:04}:{self.end_col+1:03}'

    def expand(self, pos:'Pos') -> 'Pos': # type: ignore
      line = self.line
      col = self.col
      end_line = self.end_line
      end_col = self.end_col
      if line < 0 or line > pos.line: line = pos.line
      if line == pos.line and (col < 0 or col > pos.col): col = pos.col
      if end_line < pos.end_line: end_line = pos.end_line
      if end_line == pos.end_line and end_col < pos.end_col: end_col = pos.end_col
      return Syntax.Pos(line=line, col=col, end_line=end_line, end_col=end_col)

  @staticmethod
  def path_with_slash(path:str) -> str:
    '''
    'VSCode does not recognize paths unless they contain a slash,
    so add a leading `./` to any simple name that does not look special.
    '''
    return path if ('<' in path or '/' in path) else './' + path

  @staticmethod
  def diagnostic(path:str, *, line:int, col:int, end_line=-1, end_col=-1, msg='') -> str:
    s = ' ' if msg else ''
    return f'{Syntax.path_with_slash(path)}:{Syntax.Pos(line=line, col=col, end_line=end_line, end_col=end_col)}:{s}{msg}'

  path: str
  pos: Pos
  kind: str
  content: Any


  @property
  def children(self) -> Iterator['Syntax']:
    if isinstance(self.content, str): return iter(())
    try: return iter(self.content)
    except TypeError: return iter(())

  def get_children(self) -> Iterator['Syntax']:
    'Function alias of the `children` property. Provided for ease of use with `pithy.tree.transform_tree`.'
    return self.children


  def describe(self, *, prefix='', depth=0) -> Iterator[str]:
    'Generate lines (without terminating newlines) describing the receiver.'
    spaces = '  ' * depth
    kind = f' {self.kind}:' if self.kind else ''
    content = self.content
    if isinstance(content, str):
      if len(content) <= 64:
        text = f' {content!r}'
      else:
        text = f' {content[:32]!r} … {content[-32:]!r}'
    else:
      text = ''
    yield f'{prefix}{Syntax.path_with_slash(self.path)}:{self.pos}:{spaces}{kind}{text}'
    for child in self.children:
      yield from child.describe(prefix=prefix, depth=depth+1)
