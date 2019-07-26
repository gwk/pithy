# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from . import Syntax
from ..dispatch import dispatched
from ..io import errL, errSL
from ..tree import transform_tree, OmitNode
from dataclasses import dataclass
from typing import Iterable, Iterator, List, Optional, Tuple, Union
import re

from docutils import frontend as _frontend
from docutils import nodes as _nodes
from docutils.nodes import Node as Node, Text
from docutils.utils import new_document as _new_document
from docutils.parsers.rst import Parser as _RstParser


def parse_rst(path:str, text:str) -> Syntax:
  parser = _RstParser()
  settings = _frontend.OptionParser(components=(_RstParser,)).get_default_values()
  document = _new_document(path, settings=settings)
  parser.parse(text, document)
  ctx = _Ctx(path=path, text=text, lines=text.splitlines(keepends=True))
  return transform_tree(document, _get_children, ctx.visit)


@dataclass
class Ref:
  text: Syntax
  target: Optional[Syntax]

  def __iter__(self):
    yield self.text
    if self.target: yield self.target


def _get_children(node:Node) -> Iterable[Node]:
  return node.children # type: ignore


@dataclass
class _Ctx:
  path: str
  text: str
  lines: List[str]
  line: int = 0
  col: int = 0

  @property
  def curr_line_text(self) -> str: return self.lines[self.line]

  def match_text(self, text:str, skip_leading:bool, label:str, raises=False) -> Syntax.Pos:
    'Match a single line of text, advancing self.line and self.col.'
    if skip_leading:
      while rst_syntax_re.fullmatch(self.curr_line_text, self.col):
        #errL(f'SKIPPED: {self.curr_line_text[self.col:]!r}')
        self.line += 1
        self.col = 0
    line = self.line
    col = self.curr_line_text.find(text, self.col)
    if col == -1:
      if raises: raise ValueError(text)
      errL(Syntax.diagnostic(self.path, line=self.line, col=self.col,
        msg=f'warning: {label} not matched: {text!r}\n  {self.curr_line_text!r}'))
      col = self.col # better than nothing.
      end_col = -1
    else: # matched.
      end_col = col+len(text)
      if text.endswith('\n'):
        self.line +=1
        self.col = 0
      else:
        self.col = end_col
      #errL(f'MATCHED: {self.line}:{self.col}: {text!r}')
    return Syntax.Pos(line=line, col=col, end_line=self.line, end_col=end_col)


  @dispatched
  def visit(self, node:Node, stack:Tuple[Node, ...], children:List[Node]) -> Syntax:
    'Default visitor.'
    pos = Syntax.Pos(line=(-1 if node.line is None else node.line-1), enclosed=children)
    return Syntax(path=self.path, pos=pos, kind=_kind_for(node), content=children)


  @dispatched # type: ignore
  def visit(self, node:Text, stack:Tuple[Node, ...], children:List[Node]) -> Syntax:
    'Text visitor. Determines line/col position post-hoc, which docutils does not provide.'
    assert node.line is None # Text never has line number.
    text = node.astext()
    text_lines = text.splitlines(keepends=True)
    if len(text_lines) == 1:
      pos = self.match_text(text, skip_leading=True, label='text')
      return Syntax(path=self.path, pos=pos, kind='text', content=text)
    # multiline text blocks.
    children = []
    for i, text_line in enumerate(text_lines):
      is_lead = not i
      label = 'lead multiline text' if is_lead else 'tail multiline text'
      pos = self.match_text(text_line, skip_leading=is_lead, label=label)
      children.append(Syntax(path=self.path, pos=pos, kind='text', content=text_line))
    pos = Syntax.Pos(enclosed=children)
    return Syntax(path=self.path, pos=pos, kind='lines', content=tuple(children))


  @dispatched # type: ignore
  def visit(self, node:_nodes.reference, stack:Tuple[Node, ...], children:List[Node]) -> Syntax:
    assert len(children) == 1
    text = children[0]
    assert isinstance(text, Syntax)
    attrs = node.attributes
    uri = attrs.get('refuri')
    target = None
    if uri:
      try: pos = self.match_text(uri, skip_leading=True, label='ref uri', raises=True)
      except ValueError: pass # might have been extracted from the text.
      else: target = Syntax(path=self.path, pos=pos, kind='target', content=uri)
    pos = Syntax.Pos(enclosed=(text, target))
    content = Ref(text=text, target=target)
    return Syntax(path=self.path, pos=pos, kind='ref', content=content)


  @dispatched # type: ignore
  def visit(self, node:_nodes.target, stack:Tuple[Node, ...], children:List[Node]) -> None:
    raise OmitNode


rst_syntax_re = re.compile(r'[~=\s\-_<>`:]*') # matches lines that are only markup syntax and not content.


def _kind_for(node:Node) -> str: return type(node).__name__
