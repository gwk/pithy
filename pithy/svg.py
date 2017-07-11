# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
SVG writer.
TODO: proper xml escaping.
'''

from sys import stdout
from typing import *
from typing import TextIO


FileOrPath = Union[TextIO, str]
Num = Union[int, float]
ViewBox = Union[None, Tuple[Num, Num], Tuple[Num, Num, Num, Num], Tuple[Tuple[Num, Num], Tuple[Num, Num]]]


class SvgWriter:

  def __init__(self, w:Num=None, h:Num=None, vx:Num=None, vy:Num=None, vw:Num=None, vh:Num=None, file_or_path:FileOrPath=stdout) -> None:
    self._stack: List[Tuple[int, str]] = []
    if isinstance(file_or_path, str):
      self.file = open(file_or_path, 'w')
    else:
      self.file = file_or_path
    if w is None and h is None:
      self.viewport = ''
    else:
      assert w > 0
      assert h > 0
      self.viewport = f' width="{w}" height="{h}"'
    if vx is None and vy is None and vw is None and vh is None:
      self.viewBox = ''
    else:
      if vx is None: vx = 0
      if vy is None: vy = 0
      assert vw > 0
      assert vh > 0
      self.viewBox = f' viewBox="{vx} {vy} {vw} {vh}"'

  def __del__(self) -> None:
    if self._stack:
      raise Exception(f'SvgWriter finalized before tag stack was popped; did you forget to use a `with` context?')

  def __enter__(self) -> 'SvgWriter':
    # TODO: xlink? 'xmlns:xlink="http://www.w3.org/1999/xlink"'
    vb = ''
    self.write(f'<svg xmlns="http://www.w3.org/2000/svg"{self.viewport}{self.viewBox}>')
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


  def write(self, *items):
    print('  ' * self.indent, *items, sep='', file=self.file)


  def leaf(self, tag:str, **attrs):
    self.write(f'<{tag}{_fmt_attrs(attrs)}/>')


  def tree(self, tag:str, **attrs) -> 'Tree':
    self.writer.write(f'<{tag}{_fmt_attrs(attrs)}>')
    return Tree(writer=self, tag=tag)


  def circle(self, pos:Tuple[Num, Num]=None, x:Num=None, y:Num=None, r:Num=None, **attrs) -> None:
    if pos is not None:
      assert x is None
      assert y is None
      x, y = pos
    assert r is not None
    self.leaf('circle', cx=x, cy=y, r=r, **attrs)


  def rect(self, x:Num=None, y:Num=None, w:Num=None, h:Num=None, **attrs) -> None:
    self.leaf('rect', x=x, y=y, width=w, height=h, **attrs)

  class Tree:

    def __init__(self, writer:'SvgWriter', tag:str) -> None:
      self.writer = writer
      self.tag = tag

    def __enter__(self) -> None:
      self.writer._stack.append((id(self), self.tag)) # use id to avoid ref cycle.
      return None

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
      exp = self.writer._stack.pop()
      act = (id(self), self.tag)
      if act != exp:
        raise Exception(f'SvgWriter top-of-stack {exp} does not match context: {act}')
      self.writer.write(f'</{self.tag}')


def _fmt_attrs(attrs: Dict[str, Any]) -> str:
  for k in [k for k, v in attrs.items() if v is None]:
    attrs[k] = 'none'
  if not attrs: return ''
  try: cls = attrs.pop('class_')
  except KeyError: pass
  else: attrs['class'] = cls
  return ' ' + ' '.join(f'{k}="{v}"' for k, v in attrs.items())
