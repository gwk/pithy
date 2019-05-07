# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
XML tools.
'''

import re
from typing import (Any, Callable, ContextManager, Dict, FrozenSet, Generator, Iterable, Iterator, List, Match, Optional, Tuple,
  Type, TypeVar, Union, cast)
from xml.etree.ElementTree import Element

from ..desc import repr_lim
from ..exceptions import DeleteNode, FlattenNode, MultipleMatchesError, NoMatchError
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

  void_elements:FrozenSet[str] = frozenset()
  replaced_attrs:Dict[str,str] = {}
  ws_sensitive_tags:FrozenSet[str] = frozenset()


  def __init__(self, items:Iterable[XmlItem]=(), **attrs:Any) -> None:
    super().__init__(items, **attrs)
    self.setdefault(None, '')


  def __repr__(self) -> str: return f'{type(self).__name__}{self}'


  def __str__(self) -> str:
    words = ' '.join(xml_item_summary(k, v) for k, v in self.items())
    return f'<{words}>'


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
  def substantial_child_items(self) -> Iterator[XmlChildItem]:
    return ((k, v) for k, v in self.items() if isinstance(k, int) and not (isinstance(v, str) and html_ws_re.fullmatch(v)))

  @property
  def substantial_children(self) -> Iterator[XmlChild]:
    return (v for k, v in self.items() if isinstance(k, int) and not (isinstance(v, str) and html_ws_re.fullmatch(v)))


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
        children[i] = html_ws_re.sub(replacement, v)

    self.update(enumerate(children)) # Replace children with fresh, compacted indices.


  def all(self, *, tag:str=None, cl:str=None, text:str=None, attrs:Dict[str,str]={}, **_attrs:str) -> Iterator['Xml']:
    pred = xml_predicate(tag=tag, cl=cl, text=text, attrs=attrs, _attrs=_attrs)
    for k, v in self.items():
      if isinstance(k, int) and isinstance(v, Xml) and pred(v):
        yield v

  def _find_all(self, pred:Callable[['Xml'],bool]) -> Iterator['Xml']:
    for k, v in self.items():
      if isinstance(k, int) and isinstance(v, Xml):
        if pred(v):
          yield v
        else:
          yield from v._find_all(pred)


  def find_all(self, *, tag:str=None, cl:str=None, text:str=None,
   attrs:Dict[str,str]={}, **_attrs:str) -> Iterator['Xml']:
    pred = xml_predicate(tag=tag, cl=cl, text=text, attrs=attrs, _attrs=_attrs)
    return self._find_all(pred=pred)


  def first(self, *, tag:str=None, cl:str=None, text:str=None, attrs:Dict[str,str]={}, **_attrs:str) -> 'Xml':
    try: return next(self.all(tag=tag, cl=cl, text=text, attrs=attrs, **_attrs))
    except StopIteration: pass
    raise NoMatchError(f'tag={tag!r}, cl={cl!r}, text={text!r}, attrs={attrs}, **{_attrs}; node={self}')

  def find(self, *, tag:str=None, cl:str=None, text:str=None, attrs:Dict[str,str]={}, **_attrs:str) -> 'Xml':
    try: return next(self.find_all(tag=tag, cl=cl, text=text, attrs=attrs, **_attrs))
    except StopIteration: pass
    raise NoMatchError(f'tag={tag!r}, cl={cl!r}, text={text!r}, attrs={attrs}, **{_attrs}; node={self}')


  def summary_texts(self, _needs_space:bool=True) -> Generator[str,None,bool]:
    for child in self.children:
      if isinstance(child, Xml):
        _needs_space = yield from child.summary_texts(_needs_space=_needs_space)
        continue
      for m in html_ws_split_re.finditer(str(child)):
        if m.lastgroup == 'space':
          if _needs_space:
            yield ' '
            _needs_space = False
        else:
          yield m[0]
          _needs_space = True
    return _needs_space


  def summary_text(self, limit=0) -> str:
    if not limit: return ''.join(self.summary_texts())
    parts:List[str] = []
    length = 0
    for part in self.summary_texts():
      parts.append(part)
      length += len(part)
      if length > limit: break
    return ''.join(parts)[:limit]


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


  def visit(self, *, pre:Callable[['Xml'],None]=None, post:Callable[['Xml'],None]=None) -> None:
    if pre is not None: pre(self)
    for k, v in tuple(self.items()):
      if isinstance(v, Xml): # Child element.
        try: v.visit(pre=pre, post=post)
        except DeleteNode:
          del self[k]
        except FlattenNode:
          del self[k]
          self.add_all(v.children)
    if post is not None: post(self)


def xml_item_summary(key:XmlKey, val:XmlChild, text_limit=32, attrs=False) -> str:
  if key is None: return f'{val}:' # Tag is stored under None.
  if isinstance(key, str):
    ks = key if _word_re.fullmatch(key) else repr(key)
    if attrs or key in ('id', 'class'): return f'{ks}={val!r}' # Show id and class values.
    return f'{ks}=…' # Omit other attribute values.
  if isinstance(val, Xml):
    text = val.summary_text(limit=text_limit+1)
    if text: return f'{val.tag}:{repr_lim(text, limit=text_limit)}'
    else: return val.tag
  text = html_ws_re.sub(newline_or_space_for_ws, val)
  return repr_lim(text, limit=text_limit)


def xml_predicate(*, tag:Optional[str], cl:Optional[str], text:Optional[str], attrs:Dict[str,str], _attrs:Dict[str,str]) -> Callable[[Xml],bool]:
  'Update _attrs with items from other arguments, then construct a predicate that tests Xml nodes.'

  def add(k:str, v:str) -> None:
    if _attrs.get(k, v) != v: raise ValueError('conflicting selectors for {k!r}: {v!r} != {_attrs[k]!r}')
    _attrs[k] = v

  if tag is not None: # Test for tag handled specially due to None key.
    if not tag: raise ValueError('`tag` should not be empty')
    add(None, tag) # type: ignore # Special exception for the tag's None key.
  for k, v in attrs.items():
    add(k, v)

  def predicate(node:Xml) -> bool:
    return (
      (cl is None or cl in node.classes) and
      all(node.get(ak) == av for ak, av in _attrs.items()) and
      (not text or text in node.text))

  return predicate


def newline_or_space_for_ws(match:Match) -> str:
  return '\n' if '\n' in match[0] else ' '

# HTML defines ASCII whitespace as "U+0009 TAB, U+000A LF, U+000C FF, U+000D CR, or U+0020 SPACE."
html_ws_re = re.compile(r'[\t\n\f\r ]+')
html_ws_split_re = re.compile(r'(?P<space>[\t\n\f\r ])|[^\t\n\f\r ]+')

_word_re = re.compile(r'[-\w]+')
