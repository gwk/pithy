# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Iterator, List, Tuple
from ..dataclasses import dataclass
from ..dispatch import dispatched
from ..tree import transform_tree
from . import Syntax

import docutils.frontend as _frontend # type: ignore
import docutils.nodes as _nodes
from docutils.nodes import Node, Text # type: ignore
from docutils.utils import new_document as _new_document # type: ignore
from docutils.parsers.rst import Parser as _RstParser # type: ignore


def parse(path:str, text:str) -> Syntax:
  parser = _RstParser()
  settings = _frontend.OptionParser(components=(_RstParser,)).get_default_values()
  document = _new_document(path, settings=settings)
  parser.parse(text, document)
  ctx = Ctx(path=path, text=text, lines=text.split('\n'))
  return transform_tree(document, _get_children, ctx.visit)


@dataclass
class RefTarget:
  ref: _nodes.reference
  target: _nodes.target

  @property
  def children(self):
    yield from self.ref.children
    yield from self.target.children


def _get_children(node:Node) -> Iterator[Node]:
  it = iter(node.children)
  for c in it:
    if isinstance(c, _nodes.reference):
      n = next(it)
      if isinstance(n, _nodes.target):
        yield RefTarget(c, n)
      else:
        yield c
        yield n
    else:
      yield c


@dataclass
class Ctx:
  path: str
  text: str
  lines: List[str]
  text_line: int = 0
  text_col: int = 0

  @dispatched
  def visit(self, node:Node, stack:Tuple[Node, ...], children:List[Node]) -> Syntax:
    pos = Syntax.Pos(line=(-1 if node.line is None else node.line-1), enclosed=(c.pos for c in children))
    return Syntax(path=self.path, pos=pos, kind=kind_for(node), text='', children=children)

  @dispatched
  def visit(self, node:Text, stack:Tuple[Node, ...], children:List[Node]) -> Syntax:
    text = node.astext()
    if self.text_line >= 0: # No missing text yet; attempt to find line and column of this text.
      while self.text_line < len(self.lines):
        line_text = self.lines[self.text_line]
        col = line_text.find(text[0], self.text_col) # Questionable: search for first character only.
        if col >= 0:
          self.text_col = col
          break
        else:
          self.text_line += 1
          self.text_col = 0
      if self.text_line == len(self.lines): # not found.
        errL(f'warning: text matching failed: {node}')
        self.text_line = -1
        self.text_col = -1
    pos = Syntax.Pos(line=self.text_line, col=self.text_col)
    return Syntax(path=self.path, pos=pos, kind=kind_for(node), text=text, children=())

  @dispatched
  def visit(self, node:RefTarget, stack:Tuple[Node, ...], children:List[Node]) -> Syntax:
    pos = Syntax.Pos(enclosed=(c.pos for c in children))
    return Syntax(path=self.path, pos=pos, kind=kind_for(node), text='', children=children)


def kind_for(node:Node) -> str: return type(node).__name__
