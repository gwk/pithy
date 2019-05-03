# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
XML tools.
'''

import re
from typing import Any, Callable, ContextManager, Dict, FrozenSet, Iterable, Iterator, List, Tuple, Type, TypeVar, Union, cast
from xml.etree.ElementTree import Element

from ..desc import repr_lim
from ..exceptions import DeleteNode
from .escape import fmt_attr_items


# Handle lxml comments if available; these are produced by html5_parser.
try: from lxml.etree import Comment  # type: ignore
except ImportError: Comment = type(Ellipsis)



XmlKey = Union[None,str,int] # Tag is stored under None; attrs under `str` keys; children under `int` keys.
XmlChild = Union[str,'Xml']

XmlItem = Tuple[XmlKey,XmlChild]
XmlAttrItem = Tuple[str,str]
XmlChildItem = Tuple[int,XmlChild]

_Xml = TypeVar('_Xml', bound='Xml')
_XmlChild = TypeVar('_XmlChild', bound='XmlChild')


class Xml(Dict[Union[XmlKey],XmlChild], ContextManager):
  '''
  XmlWriter is the root class for building document trees for output.
  XmlWriter is subclassed to provide more convenient Python APIs; see pithy.html and pithy.svg.
  '''

  type_name = 'Xml'
  void_elements:FrozenSet[str] = frozenset()
  replaced_attrs:Dict[str,str] = {}
  ws_sensitive_tags:FrozenSet[str] = frozenset()

  def __init__(self, items:Iterable[XmlItem]=(), **attrs:Any) -> None:
    super().__init__(items, **attrs)
    self.setdefault(None, '')

  def __repr__(self) -> str: return f'{self.type_name}({super().__repr__()})'

  @classmethod
  def new(Class:Type[_Xml], tag:str, *children:XmlChild, **attrs:str) -> _Xml:
    xml = Class()
    xml.tag = tag
    xml.update(attrs) # type: ignore
    xml.update(enumerate(children))
    return xml

  @classmethod
  def from_raw(Class:Type[_Xml], raw:Dict) -> _Xml:
    xml = Class()
    if raw:
      for k, v in raw.items():
        if isinstance(k, str):
          if k == '': k = None
          xml[k] = str(v)
        elif not isinstance(k, int):
          raise ValueError(f'Xml key must be `str` or `int`; received: {k!r}')
        if isinstance(v, (str, Xml)):
          xml[k] = v
        elif isinstance(v, dict):
          xml[k] = Class.from_raw(v)
        else:
          raise ValueError(f'Xml value must be `str`, `Xml`, or `dict`; received: {v!r}')
    return xml


  @classmethod
  def from_etree(Class:Type[_Xml], el:Element, comment_tag:str=None) -> _Xml:
    xml = Class()
    tag = el.tag
    if tag == Comment: # Weird, but this is what html5_parser produces.
      tag = comment_tag or '!COMMENT'
    xml[None] = tag
    xml.update(sorted(el.items())) # Attrs.
    # Enumerate children.
    idx = 0
    text = el.text
    if text:
      xml[idx] = text
      idx += 1
    for child in el:
      xml[idx] = Class.from_etree(child, comment_tag=comment_tag)
      idx += 1
      text = child.tail
      if text:
        xml[idx] = text
        idx += 1
    return xml


  @property
  def tag(self) -> str: return cast(str, self[None])

  @tag.setter
  def tag(self, tag:str) -> None: self[None] = tag


  @property
  def attrs(self) -> Iterator[XmlAttrItem]:
    return (p for p in self.items() if isinstance(p[0], str)) # type: ignore

  @property
  def child_items(self) -> Iterator[XmlChildItem]:
    return (p for p in self.items() if isinstance(p[0], int)) # type: ignore

  @property
  def children(self) -> Iterator[XmlChild]:
    return (v for k, v in self.items() if isinstance(k, int))

  @property
  def has_children(self) -> bool: return any(isinstance(k, int) for k in self)

  @property
  def nodes(self) -> Iterator['Xml']:
    return (v for k, v in self.items() if isinstance(v, Xml))

  @property
  def texts(self) -> Iterator[str]:
    for k, v in self.items():
      if not isinstance(k, int): continue
      if isinstance(v, str): yield v
      else: yield from v.texts

  @property
  def text(self) -> str:
    return ''.join(self.texts)


  @property
  def cl(self) -> str: return cast(str, self.get('class', ''))

  @cl.deleter
  def cl(self) -> None: del self['class']

  @cl.setter
  def cl(self, val:str) -> None: self['class'] = val

  @property
  def classes(self) -> List[str]: return cast(str, self.get('class', '')).split()

  @classes.deleter
  def classes(self) -> None: del self['class']

  @classes.setter
  def classes(self, val:Union[str, Iterable[str]]) -> None:
    if not isinstance(val, str): val = ' '.join(val)
    self['class'] = val


  @property
  def id(self) -> str: return cast(str, self.get('id', ''))


  def add(self, child:_XmlChild) -> _XmlChild:
    i = 0
    while i in self: i += 1
    self[i] = child
    return child


  def add_all(self, children:Iterable[_XmlChild]) -> None:
    i = 0
    while i in self: i += 1
    for i, child in enumerate(children, i):
      self[i] = child


  def clean(self, deep=True) -> None:
    # Get all children, consolidating consecutive strings, and simultaneously remove all children from the node.
    children:List[XmlChild] = []
    for k, v in tuple(self.items()):
      if not isinstance(k, int): continue
      del self[k]
      if isinstance(v, str): # Text.
        if not v: continue # Omit empty strings.
        if children and isinstance(children[-1], str): # Consolidate.
          children[-1] += v
        else:
          children.append(v)
      elif isinstance(v, Xml): # Child element.
        if deep: v.clean()
        children.append(v)
      else:
        raise ValueError(v)

    if self.tag not in self.ws_sensitive_tags: # Clean whitespace.
      for i in range(len(children)):
        v = children[i]
        if not isinstance(v, str): continue
        replacement = '\n' if '\n' in v else ' '
        children[i] = ws_re.sub(replacement, v)

    self.update(enumerate(children)) # Replace children with fresh, compacted indices.


  def discard(self, attr:str) -> None:
    try: del self[attr]
    except KeyError: pass


  def render(self) -> Iterator[str]:
    self_closing = not self.has_children and (not self.void_elements or (self.tag in self.void_elements))

    attrs_str = fmt_attr_items(self.attrs, self.replaced_attrs)
    head_slash = '/' if self_closing else ''
    yield f'<{self.tag}{attrs_str}{head_slash}>'

    if not self_closing:
      for child in self.children:
        if isinstance(child, Xml):
          yield from child.render()
        else:
          yield str(child)
      yield f'</{self.tag}>'


  def visit(self, visitor:Callable[['Xml'],None]) -> None:
    visitor(self)
    for k, v in tuple(self.items()):
      if isinstance(v, Xml): # Child element.
        try: v.visit(visitor)
        except DeleteNode: del self[k]


ws_re = re.compile(r'\s+')

# HTML defines ASCII whitespace as "U+0009 TAB, U+000A LF, U+000C FF, U+000D CR, or U+0020 SPACE."
html_ws_re = re.compile(r'[\t\n\f\r ]+')
