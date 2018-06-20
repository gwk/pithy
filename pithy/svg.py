# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
SVG writer.
'''

from sys import stdout
from html import escape as html_escape
from itertools import chain
from types import TracebackType
from typing import Any, ContextManager, Dict, List, Optional, TextIO, Tuple, Type, Union


FileOrPath = Union[TextIO, str]
Dim = Union[int, float, str]
Num = Union[int, float]
Point = Tuple[Num, Num]

ViewBox = Union[None, Point, Tuple[Num, Num, Num, Num], Tuple[Point, Point]] # TODO: currently unused.


class SvgWriter(ContextManager):
  '''
  SvgWriter is a ContextManager class that outputs SVG code to a file (stdout by default).
  It maintains a stack of Tree objects that guarantee proper XML tree structure.
  '''

  class Tree:
    '''
    A Tree represents non-leaf node of the SVG tree.
    '''

    def __init__(self, writer:'SvgWriter', tag:str) -> None:
      self.writer = writer
      self.tag = tag

    def __enter__(self) -> None:
      self.writer._stack.append((id(self), self.tag)) # use id to avoid ref cycle.
      return None

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc_value: Optional[BaseException],
    traceback: Optional[TracebackType]) -> None:
      exp = self.writer._stack.pop()
      act = (id(self), self.tag)
      if act != exp:
        raise Exception(f'SvgWriter top-of-stack {exp} does not match context: {act}')
      self.writer.write(f'</{self.tag}>')


  def __init__(self, file_or_path:FileOrPath=stdout, w:Dim=None, h:Dim=None, vx:Num=None, vy:Num=None, vw:Num=None, vh:Num=None) -> None:
    self._stack: List[Tuple[int, str]] = []
    if isinstance(file_or_path, str):
      self.file = open(file_or_path, 'w')
    else:
      self.file = file_or_path
    if w is None or h is None:
      self.viewport = ''
    else:
      self.viewport = f' width="{w}" height="{h}"'
    if vx is None and vy is None and vw is None and vh is None:
      self.viewBox = ''
    else:
      if vx is None: vx = 0
      if vy is None: vy = 0
      assert vw is not None and vw > 0
      assert vh is not None and vh > 0
      self.viewBox = f' viewBox="{vx} {vy} {vw} {vh}"'


  def __del__(self) -> None:
    if self._stack:
      raise Exception(f'SvgWriter finalized before tag stack was popped; did you forget to use a `with` context?')


  def __enter__(self) -> 'SvgWriter':
    self.write(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" {self.viewport}{self.viewBox}>')
    return self


  def __exit__(self, exc_type, exc_val, exc_tb) -> None:
    if exc_type is not None: return # propagate exception.
    if self._stack:
      raise Exception(f'SvgWriter context exiting with non-empty stack: {self._stack}')
    self.write('</svg>')
    return None


  @property
  def indent(self) -> int:
    return len(self._stack)


  def write(self, *items: Any) -> None:
    print('  ' * self.indent, *items, sep='', file=self.file)


  def leaf(self, tag:str, title:str=None, **attrs: Any) -> None:
    'Output a non-nesting SVG element.'
    if title is None:
      self.write(f'<{tag}{_fmt_attrs(attrs)}/>')
    else:
      self.leafText(tag, text='', title=title, **attrs)


  def leafText(self, tag:str, text:str, title:str=None, **attrs: Any) -> None:
    'Output a non-nesting SVG element that contains text between the open and close tags.'
    title_code = '' if title is None else f'<title>{_esc(title)}</title>'
    self.write(f'<{tag}{_fmt_attrs(attrs)}>{title_code}{_esc(text)}</{tag}>')


  def tree(self, tag:str, title:str=None, **attrs: Any) -> 'SvgWriter.Tree':
    'Create an SvgWriter.Tree for use in a `with` context to represent a nesting SVG element.'
    title_code = '' if title is None else f'<title>{_esc(title)}</title>'
    self.write(f'<{tag}{_fmt_attrs(attrs)}>{title_code}')
    return SvgWriter.Tree(writer=self, tag=tag)

  # SVG Elements.

  def circle(self, pos:Point=None, x:Num=None, y:Num=None, r:Num=None, **attrs) -> None:
    'Output an SVG `circle` element.'
    if pos is not None:
      assert x is None
      assert y is None
      x, y = pos
    _opt_attrs(attrs, cx=x, cy=y, r=r)
    self.leaf('circle', **attrs)


  def defs(self) -> 'SvgWriter.Tree':
    'Output an SVG `defs` element.'
    return self.tree('defs')


  def g(self, **attrs) -> 'SvgWriter.Tree':
    'Create an SVG `g` element for use in a context manager.'
    return self.tree('g', **attrs)


  def image(self, pos:Point=None, x:Num=None, y:Num=None, size:Point=None, w:Num=None, h:Num=None, **attrs) -> None:
    'Output an SVG `defs` element.'
    if pos is not None:
      assert x is None
      assert y is None
      x, y = pos
    if size is not None:
      assert w is None
      assert h is None
      w, h = size
    _opt_attrs(attrs, x=x, y=y, width=w, height=h)
    self.leaf('image', **attrs)


  def line(self, a: Point, b: Point, **attrs) -> None:
    'Output an SVG `defs` element.'
    _opt_attrs(attrs, x1=a[0], y1=a[1], x2=b[0], y2=b[1])
    self.leaf('line', **attrs)


  def marker(self, id:str, w:Num=None, h:Num=None, x:Num=None, y:Num=None, markerUnits='strokeWidth', orient:str='auto',
   **attrs) -> 'SvgWriter.Tree':
    'Output an SVG `marker` element.'
    assert w is not None
    assert h is not None
    assert x is not None
    assert y is not None
    return self.tree('marker', id=id, markerWidth=w, markerHeight=h, refX=x, refY=y, markerUnits=markerUnits, orient=orient, **attrs)


  def path(self, *commands, **attrs) -> None:
    'Output an SVG `path` element.'
    assert 'd' not in attrs
    d = ' '.join(commands)
    self.leaf('path', d=d, **attrs)


  def rect(self, pos:Point=None, x:Num=None, y:Num=None, size:Point=None, w:Num=None, h:Num=None, rx:Num=None, ry:Num=None, **attrs) -> None:
    'Output an SVG `rect` element.'
    if pos is not None:
      assert x is None
      assert y is None
      x, y = pos
    if size is not None:
      assert w is None
      assert h is None
      w, h = size
    _opt_attrs(attrs, x=x, y=y, width=w, height=h, rx=rx, ry=ry)
    self.leaf('rect', **attrs)


  def style(self, text: str, **attrs,) -> None:
    'Output an SVG `style` element.'
    self.leafText('style', text.strip(), **attrs)


  def symbol(self, id: str, **attrs) -> None:
    'Output an SVG `symol` element.'
    return self.leaf('symbol', id=id, **attrs)


  def text(self, pos:Point=None, x:Num=None, y:Num=None, text=None, **attrs) -> None:
    'Output an SVG `text` element.'
    if pos is not None:
      assert x is None
      assert y is None
      x, y = pos
    _opt_attrs(attrs, x=x, y=y)
    self.leafText('text', text, **attrs)


def _esc(val: Any) -> str:
  'HTML-escape the string representation of `val`.'
  return html_escape(str(val))


def _opt_attrs(attrs: Dict[str, Any], *pairs: Tuple[str, Any], **items:Any) -> None:
  'Add the items in `*pairs` and `**items` attrs, excluding any None values.'
  for k, v in chain(pairs, items.items()):
    if v is None: continue
    attrs[k] = v


def _fmt_attrs(attrs: Dict[str, Any]) -> str:
  'Format the `attrs` dict into XML key-value attributes.'
  if not attrs: return ''
  parts: List[str] = []
  for k, v in attrs.items():
    if v is None:
      v = 'none'
    else:
      v = _replaced_attrs.get(k, v)
    parts.append(f' {_esc(k.replace("_", "-"))}="{_esc(v)}"')
  return ''.join(parts)

_replaced_attrs = {
  'class_' : 'class',
  'href': 'xlink:href', # safari Version 11.0.3 (13604.5.3) requires this, even though xlink is deprecated in svg 2 standard.
}

valid_units = frozenset({'em', 'ex', 'px', 'pt', 'pc', 'cm', 'mm', '%', ''})

def _validate_unit(unit: str):
  'Ensure that `unit` is a valid unit string.'
  if unit not in valid_units:
    raise Exception(f'Invalid SVG unit: {unit!r}; should be one of {sorted(valid_units)}')
