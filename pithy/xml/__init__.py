# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Xml type.
'''

import re
from itertools import chain
from typing import (Any, Callable, Dict, FrozenSet, Generator, Iterable, Iterator, List, Match, Optional, Tuple, Type, TypeVar,
  Union, cast, overload)
from xml.etree.ElementTree import Element

from ..desc import repr_lim
from ..exceptions import DeleteNode, FlattenNode, MultipleMatchesError, NoMatchError, ConflictingValues
from .escape import fmt_attr_items


# Handle lxml comments if available; these are produced by html5_parser.
try: from lxml.etree import Comment  # type: ignore
except ImportError: Comment = type(Ellipsis)


XmlAttrs = Dict[str,Any]
XmlAttrItem = Tuple[str,Any]

XmlChild = Union[str,'Xml']
XmlChildren = List[XmlChild]

_Xml = TypeVar('_Xml', bound='Xml')
_XmlChild = TypeVar('_XmlChild', bound='XmlChild')

XmlPred = Callable[['Xml'],bool]
XmlVisitor = Callable[['Xml'],None]


class Xml:
  '''
  Xml root class for building document trees.
  Unlike xml.etree.ElementTree.Element, child nodes and text are interleaved.
  '''

  type_tag = '' # Subclasses can specify a tag by overriding `type_tag`.
  tag_types:Dict[str,Type['Xml']] = {}
  void_elements:FrozenSet[str] = frozenset()
  replaced_attrs:Dict[str,str] = {}
  ws_sensitive_tags:FrozenSet[str] = frozenset()

  __slots__ = ('tag', 'attrs', 'ch', '_orig', '_parent')


  def __init__(self:_Xml, *, tag:str='', attrs:XmlAttrs=None, ch:Iterable[XmlChild]=(), cl:Iterable[str]=None,
   _orig:_Xml=None, _parent:'Xml'=None, **kw_attrs:Any) -> None:
    '''
    Note: the initializer uses `attrs` dict and `ch` list references if provided, resulting in data sharing.
    This is done for two reasons:
    * avoid excess copying during deserialization from json, msgpack, or similar;
    * allow for creation of subtree nodes (with _orig/_parent set) that alias the `attr` and `ch` collections.

    Normally, nodes do not hold a reference to parent; this makes Xml trees acyclic.
    However, various Xml methods have a `traversable` option, which will return subtrees with the _orig/_parent refs set.
    Such "subtree nodes" can use the `next` and `prev` methods in addition to `pick` and friends.
    '''

    if not isinstance(tag, str): raise TypeError(tag)
    tag = tag or self.type_tag
    if not tag: raise ValueError(tag)
    self.tag = tag

    if attrs is None: attrs = kw_attrs # Important: use existing dict ref if provided.
    else: attrs.update(kw_attrs)
    self.attrs = attrs

    if cl is not None:
      if not isinstance(cl, str): cl = ' '.join(cl)
      if cl != attrs.setdefault('class', cl):
        raise ConflictingValues((attrs['class'], cl))

    self.ch:XmlChildren = ch if isinstance(ch, list) else list(ch) #^ Important: use an existing list ref if provided.

    self._orig = _orig
    self._parent = _parent


  def __repr__(self) -> str: return f'{type(self).__name__}{self}'


  def __str__(self) -> str:
    subnode = '' if self._orig is None else '$'
    words = ''.join(chain(
      (xml_attr_summary(k, v, text_limit=32, all_attrs=False) for k, v in self.attrs.items()),
      (xml_child_summary(c, text_limit=32) for c in self.ch)))
    return f'<{subnode}{self.tag}:{words}>'


  def __delitem__(self, key:str) -> Any: del self.attrs[key]

  def __getitem__(self, key:str) -> Any: return self.attrs[key]

  def __setitem__(self, key:str, val:Any) -> Any: self.attrs[key] = val

  def get(self, key:str, default=None) -> Any: return self.attrs.get(key, default)

  def __iter__(self) -> Iterator[XmlChild]: return iter(self.ch)


  @classmethod
  def from_raw(Class:Type[_Xml], raw:Dict) -> _Xml:
    'Create an Xml object (possibly subclass by tag) from a raw data dictionary.'
    tag = raw['tag']
    attrs = raw['attrs']
    raw_children = raw['ch']
    if not isinstance(tag, str): raise ValueError(tag)
    if not isinstance(attrs, dict): raise ValueError(attrs)
    for k, v in attrs.items():
      if not isinstance(k, str):
        raise ValueError(f'Xml attr key must be `str`; received: {k!r}')
    ch:XmlChildren = []
    for c in raw_children:
      if isinstance(c, (str, Xml)): ch.append(c)
      elif isinstance(c, dict): ch.append(Class.from_raw(c))
      else: raise ValueError(f'Xml child must be `str`, `Xml`, or `dict`; received: {c!r}')
    TagClass = Class.tag_types.get(tag, Class)
    return cast(_Xml, TagClass(tag=tag, attrs=attrs, ch=ch))


  @classmethod
  def from_etree(Class:Type[_Xml], el:Element) -> _Xml:
    '''
    Create an Xml object (possibly subclass by tag) from a standard library Xml element tree.
    Note: this handles lxml comment objects specially, by turning them into nodes with a '!COMMENT' tag.
    '''
    tag = el.tag
    if tag == Comment: tag = '!COMMENT' # Weird, but this is what html5_parser produces.
    # Collect children.
    attrs = el.attrib
    ch:XmlChildren = []
    text = el.text
    if text: ch.append(text)
    for child in el:
      ch.append(Class.from_etree(child))
      text = child.tail
      if text: ch.append(text)
    TagClass = Class.tag_types.get(tag, Class)
    return cast(_Xml, TagClass(tag=tag, attrs=attrs, ch=ch))


  @property
  def orig(self:_Xml) -> _Xml:
    'If this node is a query subnode, return the original; otherwise raise ValueError.'
    if self._orig is None: raise ValueError(f'node is not a subnode: {self}')
    return self._orig


  def subnode(self:_Xml, parent:'Xml') -> _Xml:
    'Create a subnode for `self` referencing the provided `parent`.'
    if self._orig is not None: raise ValueError(f'node is already a subnode: {self}')
    return type(self)(tag=self.tag, attrs=self.attrs, ch=self.ch, _orig=self, _parent=parent)


  def child_items(self, ws=False, traversable=False) -> Iterator[Tuple[int,XmlChild]]:
    'Yield (index, child) pairs. If `ws` is False, then children that are purely whitespace will be filtered out.'
    for i, c in enumerate(self.ch):
      if isinstance(c, Xml):
        yield (i, (c.subnode(self) if traversable else c))
      else:
        if not ws and html_ws_re.fullmatch(c): continue
        yield (i, c)


  def children(self, ws=False, traversable=False) -> Iterator[XmlChild]:
    'Yield child nodes and text. If `ws` is False, then children that are purely whitespace will be filtered out.'
    for c in self.ch:
      if isinstance(c, Xml):
        yield c.subnode(self) if traversable else c
      else:
        if not ws and html_ws_re.fullmatch(c): continue
        yield c


  def child_nodes(self, traversable=False) -> Iterator['Xml']:
    'Yield child Xml nodes.'
    return ((c.subnode(self) if traversable else c) for c in self.ch if isinstance(c, Xml))


  @property
  def has_substantial_children(self) -> bool:
    return any((isinstance(c, Xml) or c and not html_ws_re.fullmatch(c)) for c in self.ch)


  @property
  def texts(self) -> Iterator[str]:
    for c in self.ch:
      if isinstance(c, Xml): yield from c.texts
      else: yield c

  @property
  def text(self) -> str:
    return ''.join(self.texts)


  @property
  def cl(self) -> str: return cast(str, self.attrs.get('class', ''))

  @cl.deleter
  def cl(self) -> None: del self.attrs['class']

  @cl.setter
  def cl(self, val:str) -> None: self.attrs['class'] = val

  @property
  def classes(self) -> List[str]: return cast(str, self.attrs.get('class', '')).split()

  @classes.deleter
  def classes(self) -> None: del self.attrs['class']

  @classes.setter
  def classes(self, val:Union[str, Iterable[str]]) -> None:
    if not isinstance(val, str): val = ' '.join(val)
    self.attrs['class'] = val


  @property
  def id(self) -> str: return cast(str, self.attrs.get('id', ''))


  def append(self, child:_XmlChild) -> _XmlChild:
    if isinstance(child, Xml) and child._orig is not None: child = child._orig
    self.ch.append(child)
    return child


  def extend(self, children:Iterable[_XmlChild]) -> None:
    for el in children: self.append(el)


  def _single(self, Child_type:Type[_Xml]) -> _Xml:
    for c in self.ch:
      if isinstance(c, Child_type): return c
    return self.append(Child_type())


  def clean(self, deep=True) -> None:
    # Consolidate consecutive strings.
    ch:List[XmlChild] = []
    for c in self.ch:
      if isinstance(c, Xml):
        if deep: c.clean(deep)
      else: # Assume c is str.
        if not c: continue
        if ch and isinstance(ch[-1], str): # Consolidate.
          ch[-1] += c
          continue
      ch.append(c)

    if self.tag not in self.ws_sensitive_tags: # Clean whitespace.
      for i in range(len(ch)):
        c = ch[i]
        if not isinstance(c, str): continue
        replacement = '\n' if '\n' in c else ' '
        ch[i] = html_ws_re.sub(replacement, c)

    self.ch[:] = ch


  # Picking and finding.

  @overload
  def pick_all(self, type_or_tag:Type[_Xml], *, cl:str='', text:str='', traversable=False, **attrs:str) -> Iterator[_Xml]: ...

  @overload
  def pick_all(self, type_or_tag:str='', *, cl:str='', text:str='', traversable=False, **attrs:str) -> Iterator['Xml']: ...

  def pick_all(self, type_or_tag='', *, cl:str='', text:str='', traversable=False, **attrs:str):
    pred = xml_pred(type_or_tag=type_or_tag, cl=cl, text=text, attrs=attrs)
    return ((c.subnode(self) if traversable else c) for c in self.ch if isinstance(c, Xml) and pred(c))


  @overload
  def find_all(self, type_or_tag:Type[_Xml], *, cl:str='', text:str='', traversable=False, **attrs:str) -> Iterator[_Xml]: ...

  @overload
  def find_all(self, type_or_tag:str='', *, cl:str='', text:str='', traversable=False, **attrs:str) -> Iterator['Xml']: ...

  def find_all(self, type_or_tag='', *, cl:str='', text:str='', traversable=False, **attrs:str):
    pred = xml_pred(type_or_tag=type_or_tag, cl=cl, text=text, attrs=attrs)
    if text: return self._find_all_text(pred, traversable)
    else: return self._find_all(pred, traversable)

  def _find_all(self, pred:XmlPred, traversable:bool) -> Iterator['Xml']:
    for c in self.ch:
      if isinstance(c, Xml):
        if pred(c): yield (c.subnode(self) if traversable else c)
        yield from c._find_all(pred, traversable) # Always search ch. TODO: use generator send() to let consumer decide?

  def _find_all_text(self, pred:XmlPred, traversable:bool) -> Generator['Xml',None,bool]:
    '''
    Use post-order algorithm to find matching text, and do not search parents of matching children.
    This is desirable because the calculation of text is expensive
    and the caller most likely does not want nodes that contain each other.
    '''
    found_match = False
    for c in self.ch:
      if isinstance(c, Xml):
        child_match = yield from c._find_all_text(pred, traversable)
        if child_match:
          found_match = True
        elif pred(c):
          found_match = True
          yield (c.subnode(self) if traversable else c)
    return found_match


  @overload
  def pick_first(self, type_or_tag:Type[_Xml], *, cl:str='', text:str='', traversable=False, **attrs:str) -> _Xml: ...

  @overload
  def pick_first(self, type_or_tag:str='', *, cl:str='', text:str='', traversable=False, **attrs:str) -> 'Xml': ...

  def pick_first(self, type_or_tag='', *, cl:str='', text:str='', traversable=False, **attrs:str):
    pred = xml_pred(type_or_tag=type_or_tag, cl=cl, text=text, attrs=attrs)
    for c in self.ch:
      if isinstance(c, Xml) and pred(c): return (c.subnode(self) if traversable else c)
    raise NoMatchError(f'{fmt_xml_predicate_args(type_or_tag, cl, text, attrs)}; node: {self}')


  @overload
  def find_first(self, type_or_tag:Type[_Xml], *, cl:str='', text:str='', traversable=False, **attrs:str) -> _Xml: ...

  @overload
  def find_first(self, type_or_tag:str='', *, cl:str='', text:str='', traversable=False, **attrs:str) -> 'Xml': ...

  def find_first(self, type_or_tag='', *, cl:str='', text:str='', traversable=False, **attrs:str):
    for c in self.find_all(type_or_tag=type_or_tag, cl=cl, text=text, traversable=traversable, **attrs):
      return c
    raise NoMatchError(f'{fmt_xml_predicate_args(type_or_tag, cl, text, attrs)}; node: {self}')


  @overload
  def pick(self, type_or_tag:Type[_Xml], *, cl:str='', text:str='', traversable=False, **attrs:str) -> _Xml: ...

  @overload
  def pick(self, type_or_tag:str='', *, cl:str='', text:str='', traversable=False, **attrs:str) -> 'Xml': ...

  def pick(self, type_or_tag='', *, cl:str='', text:str='', traversable=False, **attrs:str):
    first:Optional[Xml] = None
    for c in self.pick_all(type_or_tag=type_or_tag, cl=cl, text=text, traversable=traversable, **attrs):
      if first is None: first = c
      else:
        s = fmt_xml_predicate_args(type_or_tag, cl, text, attrs)
        raise MultipleMatchesError(f'{s}; node: {self}\n  match: {first}\n  match: {c}')
    if first is None:
      raise NoMatchError(f'{fmt_xml_predicate_args(type_or_tag, cl, text, attrs)}; node: {self}')
    return first


  @overload
  def find(self, type_or_tag:Type[_Xml], *, cl:str='', text:str='', traversable=False, **attrs:str) -> _Xml: ...

  @overload
  def find(self, type_or_tag:str='', *, cl:str='', text:str='', traversable=False, **attrs:str) -> 'Xml': ...

  def find(self, type_or_tag='', *, cl:str='', text:str='', traversable=False, **attrs:str):
    first:Optional[Xml] = None
    for c in self.find_all(type_or_tag=type_or_tag, cl=cl, text=text, traversable=traversable, **attrs):
      if first is None: first = c
      else:
        s = fmt_xml_predicate_args(type_or_tag, cl, text, attrs)
        raise MultipleMatchesError(f'{s}; node: {self}\n  match: {first}\n  match: {c}')
    if first is None:
      raise NoMatchError(f'{fmt_xml_predicate_args(type_or_tag, cl, text, attrs)}; node: {self}')
    return first


  # Traversal.

  @overload
  def next(self, type_or_tag:Type[_Xml], *, cl:str='', text:str='', traversable=False, **attrs:str) -> _Xml: ...

  @overload
  def next(self, type_or_tag:str='', *, cl:str='', text:str='', traversable=False, **attrs:str) -> 'Xml': ...

  def next(self, type_or_tag='', *, cl:str='', text:str='', traversable=False, **attrs:str):
    if self._orig is None or self._parent is None: raise ValueError(f'cannot traverse non-subnode: {self}')
    pred = xml_pred(type_or_tag=type_or_tag, cl=cl, text=text, attrs=attrs)
    found_orig = False
    for c in self._parent.ch:
      if not isinstance(c, Xml): continue
      if found_orig:
        if pred(c): return (c.subnode(self._parent) if traversable else c)
      elif c is self._orig:
        found_orig = True
    if not found_orig: raise ValueError('node was removed from parent')
    raise NoMatchError(f'{fmt_xml_predicate_args(type_or_tag, cl, text, attrs)}; node: {self}')


  @overload
  def prev(self, type_or_tag:Type[_Xml], *, cl:str='', text:str='', traversable=False, **attrs:str) -> _Xml: ...

  @overload
  def prev(self, type_or_tag:str='', *, cl:str='', text:str='', traversable=False, **attrs:str) -> 'Xml': ...

  def prev(self, type_or_tag='', *, cl:str='', text:str='', traversable=False, **attrs:str):
    if self._orig is None or self._parent is None: raise ValueError(f'cannot traverse non-subnode: {self}')
    pred = xml_pred(type_or_tag=type_or_tag, cl=cl, text=text, attrs=attrs)
    found_orig = False
    for c in reversed(self._parent.ch):
      if not isinstance(c, Xml): continue
      if found_orig:
        if pred(c): return (c.subnode(self._parent) if traversable else c)
      elif c is self._orig:
        found_orig = True
    if not found_orig: raise ValueError('node was removed from parent')
    raise NoMatchError(f'{fmt_xml_predicate_args(type_or_tag, cl, text, attrs)}; node: {self}')


  # Text.

  def summary_texts(self, _needs_space:bool=True) -> Generator[str,None,bool]:
    for child in self.ch:
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


  # Text summary.

  def summarize(self, levels=1, indent=0) -> str:
    nl_indent = '\n' + '  ' * indent
    return ''.join(self._summarize(levels, nl_indent))

  def _summarize(self, levels:int, nl_indent:str) -> Iterator[str]:
    if levels <= 0:
      yield str(self)
    else:
      subnode = '' if self._orig is None else '$'
      attr_words = ''.join(xml_attr_summary(k, v, text_limit=32, all_attrs=False) for k, v in self.attrs.items())
      nl_indent1 = nl_indent + '  '
      yield f'<{subnode}{self.tag}:{attr_words}'
      for c in self.ch:
        yield nl_indent1
        if isinstance(c, Xml):
          yield from c._summarize(levels-1, nl_indent1)
        else:
          yield repr(c)
      yield '>'

  def discard(self, attr:str) -> None:
    try: del self.attrs[attr]
    except KeyError: pass


  def render(self) -> Iterator[str]:
    if self.void_elements:
      self_closing = self.tag in self.void_elements
      if self_closing and self.ch: raise ValueError(self)
    else:
      self_closing = not self.ch

    attrs_str = fmt_attr_items(self.attrs.items(), self.replaced_attrs)
    head_slash = '/' if self_closing else ''
    yield f'<{self.tag}{attrs_str}{head_slash}>'

    if not self_closing:
      for child in self.ch:
        if isinstance(child, Xml):
          yield from child.render()
        else:
          yield str(child)
      yield f'</{self.tag}>'


  def visit(self, *, pre:XmlVisitor=None, post:XmlVisitor=None, traversable=False) -> None:
    if pre is not None: pre(self)

    modified_children:List[XmlChild] = []
    first_mod_idx:Optional[int] = None
    for i, c in enumerate(self.ch):
      if isinstance(c, Xml):
        if traversable: c = c.subnode(self)
        try: c.visit(pre=pre, post=post, traversable=traversable)
        except DeleteNode:
          if first_mod_idx is None: first_mod_idx = i
          continue
        except FlattenNode:
          if first_mod_idx is None: first_mod_idx = i
          modified_children.extend(c.ch) # Insert children in place of `c`.
          continue
      if first_mod_idx is not None:
        modified_children.append(c)
    if first_mod_idx is not None:
      self.ch[first_mod_idx:] = modified_children

    if post is not None: post(self)


def xml_attr_summary(key:str, val:Any, *, text_limit:int, all_attrs:bool) -> str:
  ks = key if _word_re.fullmatch(key) else repr(key)
  if all_attrs or key in ('id', 'class'): return f' {ks}={repr_lim(val, text_limit)}' # Show id and class values.
  return f' {ks}=…' # Omit other attribute values.


def xml_child_summary(child:XmlChild, text_limit:int) -> str:
  if isinstance(child, Xml):
    text = child.summary_text(limit=text_limit)
    if text: return f' {child.tag}:{repr_lim(text, limit=text_limit)}'
    else: return ' ' + child.tag
  text = html_ws_re.sub(newline_or_space_for_ws, child)
  return ' ' + repr_lim(text, limit=text_limit)


def xml_pred(type_or_tag:Union[str,Type[_Xml]]='', *, cl:str='', text:str='', attrs:Dict[str,Any]={}) -> XmlPred:
  'Update _attrs with items from other arguments, then construct a predicate that tests Xml nodes.'

  tag_pred:Callable
  if not type_or_tag: tag_pred = lambda node: True
  elif isinstance(type_or_tag, type): tag_pred = lambda node: isinstance(node, type_or_tag) # type: ignore
  else: tag_pred = lambda node: node.tag == type_or_tag

  def predicate(node:Xml) -> bool:
    return (
      tag_pred(node) and
      (not cl or cl in node.classes) and
      all(node.attrs.get(k) == v for k, v in attrs.items()) and
      (not text or text in node.text))

  return predicate


def fmt_xml_predicate_args(type_or_tag:Union[Type,str], cl:str, text:str, attrs:Dict[str,str]) -> str:
  words:List[str] = []
  if type_or_tag: words.append(f'{type_or_tag.__name__ if isinstance(type_or_tag, type) else type_or_tag}:')
  if cl: words.append(f'cl={cl!r}')
  for k, v in attrs.items(): words.append(xml_attr_summary(k, v, text_limit=0, all_attrs=True))
  if text: words.append(f'…{text!r}…')
  return ' '.join(words)


def newline_or_space_for_ws(match:Match) -> str:
  return '\n' if '\n' in match[0] else ' '

# HTML defines ASCII whitespace as "U+0009 TAB, U+000A LF, U+000C FF, U+000D CR, or U+0020 SPACE."
html_ws_re = re.compile(r'[\t\n\f\r ]+')
html_ws_split_re = re.compile(r'(?P<space>[\t\n\f\r ])|[^\t\n\f\r ]+')

_word_re = re.compile(r'[-\w]+')
