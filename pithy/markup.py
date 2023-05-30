# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
`markup` provides the `Mu` class, a base class for representing HTML, SVG, XML, SGML, and other document tree formats.
'''

import re
from collections import Counter
from functools import wraps
from inspect import get_annotations
from itertools import chain
from typing import (Any, Callable, cast, ClassVar, Dict, Generator, Iterable, Iterator, List, Match, Optional, overload, Tuple,
  Type, TypeVar, Union)
from xml.etree.ElementTree import Element

from .exceptions import ConflictingValues, DeleteNode, FlattenNode, MultipleMatchesError, NoMatchError
from .iterable import window_iter, window_pairs
from .reprs import repr_lim
from .string import EscapedStr


# If lxml is available, import the special Comment value that is used as the tag for comments.
try: from lxml.etree import Comment
except ImportError: Comment = object() # type: ignore[assignment] # Comment is a cyfunction; fall back to a dummy object.


_T = TypeVar('_T')

# Attr values are currently Any so that we can preserve exact numerical values.
MuAttrs = Dict[str,Any]
MuAttrItem = Tuple[str,Any]

MuChild = Union[str,EscapedStr,'Mu']
MuChildren = List[MuChild]
MuChildOrChildren = Union[MuChild,Iterable[MuChild]]

MuChildLax = Union[MuChild,int,float]
MuChildrenLax = List[MuChildLax]
MuChildOrChildrenLax = Union[MuChildLax,Iterable[MuChildLax]]

_Mu = TypeVar('_Mu', bound='Mu')
_MuChild = TypeVar('_MuChild', bound='MuChild')

MuPred = Callable[[_Mu],bool]
MuVisitor = Callable[[_Mu],None]
MuIterVisitor = Callable[[_Mu],Iterator[_T]]


class Present:
  '''
  The Present class is used to only set an attribute key if `is_present` evaluates to True.
  If an attribute has a `Present(True)` value, then the markup output will have an empty value set.
  https://html.spec.whatwg.org/multipage/syntax.html#attributes-2.
  For attributes that are unconditionally set, just use `key=''`.
  '''
  def __init__(self, is_present:Any):
    self.is_present = bool(is_present)


class Mu:
  '''
  Base Markup type for HTML, SVG, XML, SGML, and other document tree formats.

  Unlike xml.etree.ElementTree.Element, child nodes and text are interleaved.

  The design primarily accommodates HTML5 and SVG but works with XML.

  Every node has a tag string, usually provided as a static override by a subclass.
  For example, the `Div` subclass represents an HTML div and defines `tag = 'div'`.

  However a parser can instead return generic `Mu` nodes with tags set per node,
  or perhaps a subclass representing invalid nodes that sets the tag per node.
  '''

  tag = '' # Subclasses can override the class tag, or give each instance its own tag attribute.

  tag_types:ClassVar[dict[str,type['Mu']]] = {} # Dispatch table mapping tag names to Mu subtypes.
  generic_tag_type:ClassVar[type['Mu']] # The subtype to use for tags that are not in `tag_types`. Set to `Mu` below.
  inline_tags:ClassVar[frozenset[str]] = frozenset() # Set of tags that should be rendered inline.
  void_tags:ClassVar[frozenset[str]] = frozenset() # Set of tags that should be rendered as "void tags" (for HTML correctness).
  ws_sensitive_tags:ClassVar[frozenset[str]] = frozenset() # Set of tags that are whitespace sensitive.
  replaced_attrs:ClassVar[Dict[str,str]] = {} # Map of attribute names to replacement values for rendering.

  attr_sort_ranks = {
    'id': -2,
    'class': -1,
  }

  __slots__ = ('attrs', '_', '_orig', '_parent')

  # Instance attributes.
  attrs:MuAttrs
  _:list[MuChild]

  def __init__(self:_Mu,
   *_mu_positional_children:MuChildLax, # Additional children can be passed as positional arguments.
   _:MuChildOrChildrenLax=(),
   tag:str='',
   cl:Iterable[str]|None=None,
   _orig:_Mu|None=None, # _orig is set by methods that are called with the `traversable` option.
   _parent:Optional['Mu']=None, # _parent is set by methods that are called with the `traversable` option.
   attrs:MuAttrs|None=None,
   **kw_attrs:Any # Additional attrs can be passed as keyword arguments. These take precedence over keys in `attrs`.
   ) -> None:
    '''
    Note: the initializer uses `attrs` dict and `_` (children) list references if provided, resulting in data sharing.
    This is done for two reasons:
    * avoid excess copying during deserialization from json, msgpack, or similar;
    * allow for creation of subtree nodes (with _orig/_parent set) that alias the `attr` and `_` collections.

    The `_` property represents the node children list, and is typed as MuChildOrChildrenLax to allow for numeric values.
    These are converted to strings during initialization.
    If the `_` argument is a list and contains numeric values, it is mutated in place.

    The `cl` initializer argument is a special shorthand for htm `class` attributes.
    It accepts an iterable of strings, which are joined with spaces and set as the `class` attribute.

    Normally, nodes do not hold a reference to parent; this makes Mu trees acyclic.
    However, various Mu methods have a `traversable` option, which will return subtrees with the _orig/_parent refs set.
    Such "subtree nodes" can use the `next` and `prev` methods in addition to `pick` and friends.
    '''

    assert 'ch' not in kw_attrs, 'Use `_` instead of `ch` for children.'

    if tag:
      if cls_tag := getattr(self, 'tag', None):
        if cls_tag != tag:
           raise ValueError(f'Mu subclass {type(self)!r} already has tag: {self.tag!r}; instance tag: {tag!r}')
      else:
        self.tag = tag

    if attrs is None: attrs = {} # Important: use existing dict ref if provided.
    for k, v in kw_attrs.items():
      attrs[k.replace('_', '-')] = v
    self.attrs = attrs

    if cl is not None:
      if not isinstance(cl, str): cl = ' '.join(filter(None, cl))
      if cl != attrs.setdefault('class', cl):
        raise ConflictingValues((attrs['class'], cl))

    self._orig = _orig
    self._parent = _parent

    if isinstance(_, mu_child_classes_lax): # Single child argument; wrap it in a list.
      children:MuChildrenLax = [_]
    elif isinstance(_, list):
      children = _ # Important: use an existing list ref if provided. This allows subnodes to alias original contents.
    else:
      children = list(_)
    for i, c in enumerate(children):
      if isinstance(c, mu_child_classes):
        continue
      if isinstance(c, _mu_child_classes_lax_converted):
        children[i] = str(c)
      else:
        raise TypeError(f'Invalid child type: {type(c)!r}; value: {repr_lim(c)!r}')

    for c in _mu_positional_children:
      if isinstance(c, _mu_child_classes_lax_converted):
        c = str(c)
      children.append(c)

    self._ = cast(list[MuChild], children)


  def __repr__(self) -> str: return f'{type(self).__name__}{self}'


  def __str__(self) -> str:
    try: # `__str__` may get called during exception handling during initialization, when attributes are not yet set.
      subnode = '' if self._orig is None else '$'
      words = ''.join(chain(
        (xml_attr_summary(k, v, text_limit=32, all_attrs=False) for k, v in self.attrs.items()),
        (xml_child_summary(c, text_limit=32) for c in self._)))
      return f'<{subnode}{self.tag}:{words}>'
    except AttributeError:
      return super().__repr__()


  def __bytes__(self) -> bytes:
    return self.render_str().encode('utf-8')


  def __delitem__(self, key:str) -> Any: del self.attrs[key]

  def __getitem__(self, key:str) -> Any: return self.attrs[key]

  def __setitem__(self, key:str, val:Any) -> Any: self.attrs[key] = val

  def get(self, key:str, default=None) -> Any: return self.attrs.get(key, default)

  def __iter__(self) -> Iterator[MuChild]: return iter(self._)


  @classmethod
  def from_raw(cls:Type[_Mu], raw:Dict) -> _Mu:
    'Create a Mu object (or possibly a subclass instance chosen by tag) from a raw data dictionary.'
    tag = raw['tag']
    attrs = raw['attrs']
    raw_children = raw['_']
    if not isinstance(tag, str): raise ValueError(tag)
    if not isinstance(attrs, dict): raise ValueError(attrs)
    for k, v in attrs.items():
      if not isinstance(k, str):
        raise ValueError(f'Mu attr key must be `str`; received: {k!r}')
    children:MuChildren = []
    TagClass = cls.tag_types.get(tag, cls.generic_tag_type)
    for c in raw_children:
      if isinstance(c, mu_child_classes): children.append(c)
      elif isinstance(c, dict): children.append(TagClass.from_raw(c))
      #^ Note: we use the dynamically chosen TagClass when recursing,
      # so that we can transition between subclass families of Mu, particularly between HTML and SVG.
      else: raise ValueError(f'Mu child must be `str`, `EscapedStr`, `Mu`, or `dict`; received: {c!r}')
    return cast(_Mu, TagClass(tag=tag, attrs=attrs, _=children))


  @classmethod
  def from_etree(cls:Type[_Mu], el:Element) -> _Mu:
    '''
    Create a Mu object (possibly subclass by tag) from a standard library element tree.
    Note: this handles lxml comment objects specially, by turning them into nodes with a '!COMMENT' tag.
    '''
    tag = el.tag
    if tag is Comment: tag = '!COMMENT' # `Comment` is a cython object; convert it to a string.
    # Collect children.
    attrs = el.attrib
    children:MuChildren = []
    text = el.text
    if text: children.append(text)
    TagClass = cls.tag_types.get(tag, cls.generic_tag_type)
    for child in el:
      children.append(TagClass.from_etree(child))
      #^ Note: we use the dynamically chosen TagClass when recursing,
      # so that we can transition between subclass families of Mu, particularly between HTML and SVG.
      text = child.tail
      if text: children.append(text)
    return cast(_Mu, TagClass(tag=tag, attrs=attrs, _=children))


  @property
  def orig(self:_Mu) -> _Mu:
    'If this node is a query subnode, return the original; otherwise raise ValueError.'
    if self._orig is None: raise ValueError(f'node is not a subnode: {self}')
    return self._orig


  @property
  def parent(self) -> 'Mu':
    'If the node is a subnode, return the parent. Otherwise raise ValueError.'
    if self._parent is None: raise ValueError(f'node is not a subnode: {self}')
    return self._parent


  def subnode(self:_Mu, parent:'Mu') -> _Mu:
    'Create a subnode for `self` referencing the provided `parent`.'
    if self._orig is not None: raise ValueError(f'node is already a subnode: {self}')
    return type(self)(tag=self.tag, attrs=self.attrs, _=self._, _orig=self, _parent=parent)


  def child_items(self, ws=False, traversable=False) -> Iterator[Tuple[int,MuChild]]:
    'Yield (index, child) pairs. If `ws` is False, then children that are purely whitespace will be filtered out.'
    for i, c in enumerate(self._):
      if isinstance(c, Mu):
        yield (i, (c.subnode(self) if traversable else c))
        continue
      if isinstance(c, EscapedStr):
        c = c.string
      if not ws and html_ws_re.fullmatch(c): continue
      yield (i, c)


  def children(self, ws=False, traversable=False) -> Iterator[MuChild]:
    'Yield child nodes and text. If `ws` is False, then children that are purely whitespace will be filtered out.'
    for c in self._:
      if isinstance(c, Mu):
        yield c.subnode(self) if traversable else c
        continue
      if isinstance(c, EscapedStr):
        c = c.string
      if not ws and html_ws_re.fullmatch(c): continue
      yield c


  def child_nodes(self, traversable=False) -> Iterator['Mu']:
    'Yield child Mu nodes.'
    return ((c.subnode(self) if traversable else c) for c in self._ if isinstance(c, Mu))


  @property
  def has_substantial_children(self) -> bool:
    'Predicate testing whether the node has non-whitespace children.'
    for c in self._:
      if isinstance(c, Mu): return True
      if isinstance(c, EscapedStr): c = c.string
      if c and not html_ws_re.fullmatch(c): return True
    return False


  @property
  def texts(self) -> Iterator[str]:
    'Yield the text of the tree sequentially.'
    for c in self._:
      if isinstance(c, str): yield c
      elif isinstance(c, Mu): yield from c.texts
      elif isinstance(c, EscapedStr): yield c.string
      else: raise TypeError(repr(c)) # Expected str, Mu, or EscapedStr.


  @property
  def text(self) -> str:
    'Return the text of the tree joined as a single string.'
    return ''.join(self.texts)


  def text_clean_ws(self, nl=False) -> str:
    'Return the text of the tree joined as a single string, with whitespace collapsed.'
    return re.sub('\s+', newline_or_space_for_ws if nl else ' ', self.text.strip())


  @property
  def cl(self) -> str:
    '`cl` is shortand for the `class` attribute.'
    return str(self.attrs.get('class', ''))

  @cl.deleter
  def cl(self) -> None: del self.attrs['class']

  @cl.setter
  def cl(self, val:str) -> None: self.attrs['class'] = val


  @property
  def classes(self) -> List[str]:
    'The `class` attribute split into individual words.'
    return cast(str, self.attrs.get('class', '')).split()

  @classes.deleter
  def classes(self) -> None: del self.attrs['class']

  @classes.setter
  def classes(self, val:Union[str, Iterable[str]]) -> None:
    if not isinstance(val, str): val = ' '.join(val)
    self.attrs['class'] = val


  def prepend_class(self, cl:str) -> None:
    try: existing = self.attrs['class']
    except KeyError: self.attrs['class'] = cl
    else: self.attrs['class'] = f'{cl} {existing}'


  def append_class(self, cl:str) -> None:
    try: existing = self.attrs['class']
    except KeyError: self.attrs['class'] = cl
    else: self.attrs['class'] = f'{existing} {cl}'


  @property
  def id(self) -> str: return str(self.attrs.get('id', ''))

  @id.setter
  def id(self, val:str) -> None: self.attrs['id'] = val

  @id.deleter
  def id(self) -> None: del self.attrs['id']


  def all_ids(self) -> set[str]:
    ids = set()
    self.visit(pre=lambda node: ids.add(node.id))
    return ids


  def unique_ids(self) -> set[str]:
    ids = Counter[str]()
    def count_ids(node:Mu) -> None:
      ids[node.id] += 1
    self.visit(pre=count_ids)
    return { id for id, count in ids.items() if count == 1 }


  def unique_id(self, unique_id_set:set[str]) -> Optional[str]:
    id = self.id
    return id if id in unique_id_set else None


  def append(self, child:_MuChild) -> _MuChild:
    if isinstance(child, Mu) and child._orig is not None:
      child = child._orig
      assert child._orig is None
    if not isinstance(child, mu_child_classes): raise TypeError(child)
    self._.append(child)
    return child # The type of child._orig is the same as child.


  def extend(self, *child_or_children:MuChildOrChildrenLax) -> None:
    for c in child_or_children:
      if isinstance(c, mu_child_classes):
        self.append(c)
      elif isinstance(c, _mu_child_classes_lax_converted):
        self.append(str(c))
      else:
        for el in c:
          if isinstance(el, _mu_child_classes_lax_converted):
            el = str(el)
          self.append(el)


  def clean(self, deep=True) -> None:
    # Consolidate consecutive strings.
    children:List[MuChild] = []
    for c in self._:
      if isinstance(c, Mu):
        if deep: c.clean(deep)
      elif isinstance(c, str):
        if not c: continue # Do not append.
        if children and isinstance(children[-1], str): # Consolidate.
          children[-1] += c
          continue # Do not append.
      else:
        raise ValueError(c) # Not mu_child_classes.
      children.append(c)

    inline_tags = self.inline_tags

    if self.tag not in self.ws_sensitive_tags:
      # Strip strings adjacent to block elements.
      for i, (p, c, n) in enumerate(window_iter(children, width=3), 1):
        if not isinstance(c, str): continue
        assert isinstance(p, Mu)
        assert isinstance(n, Mu)
        if p.tag not in inline_tags: c = c.lstrip()
        if n.tag not in inline_tags: c = c.rstrip()
        children[i] = c

      # If this element is a block, strip text at beginning and end.
      if children and self.tag not in inline_tags:
        c0 = children[0]
        if isinstance(c0, str): children[0] = c0.lstrip()
        cl = children[-1]
        if isinstance(cl, str): children[-1] = cl.rstrip()

      children = [c for c in children if c] # Filter now-empty text elements.

      # Reduce remaining, repeated whitespace down to single '\n' and ' ' characters.
      # https://www.w3.org/TR/CSS22/text.html#white-space-model
      # https://drafts.csswg.org/css-text-3/#white-space-phase-1
      for i in range(len(children)):
        c = children[i]
        if isinstance(c, str):
          children[i] = html_ws_re.sub(newline_or_space_for_ws, c)

    self._[:] = children # Mutate the original array beacuse it may be aliased by subnodes.



  # Picking and finding.

  @overload
  def pick_all(self, type_or_tag:Type[_Mu], *, cl:str='', text:str='', traversable=False, **attrs:str) -> Iterator[_Mu]: ...

  @overload
  def pick_all(self, type_or_tag:str='', *, cl:str='', text:str='', traversable=False, **attrs:str) -> Iterator['Mu']: ...

  def pick_all(self, type_or_tag='', *, cl:str='', text:str='', traversable=False, **attrs:str):
    'Pick all matching children of this node.'
    pred = xml_pred(type_or_tag=type_or_tag, cl=cl, text=text, attrs=attrs)
    return ((c.subnode(self) if traversable else c) for c in self._ if isinstance(c, Mu) and pred(c))


  @overload
  def find_all(self, type_or_tag:Type[_Mu], *, cl:str='', text:str='', traversable=False, **attrs:str) -> Iterator[_Mu]: ...

  @overload
  def find_all(self, type_or_tag:str='', *, cl:str='', text:str='', traversable=False, **attrs:str) -> Iterator['Mu']: ...

  def find_all(self, type_or_tag='', *, cl:str='', text:str='', traversable=False, **attrs:str):
    'Find matching nodes in the subtree rooted at this node.'
    pred = xml_pred(type_or_tag=type_or_tag, cl=cl, text=text, attrs=attrs)
    if text: return self._find_all_text(pred, traversable)
    else: return self._find_all(pred, traversable)

  def _find_all(self, pred:MuPred, traversable:bool) -> Iterator['Mu']:
    for c in self._:
      if isinstance(c, Mu):
        if pred(c): yield (c.subnode(self) if traversable else c)
        yield from c._find_all(pred, traversable) # Always search children. TODO: use generator send() to let consumer decide?

  def _find_all_text(self, pred:MuPred, traversable:bool) -> Generator['Mu',None,bool]:
    '''
    Use post-order algorithm to find matching text, and do not search parents of matching children.
    This is desirable because the calculation of text is expensive
    and the caller most likely does not want nodes that contain each other.
    '''
    found_match = False
    for c in self._:
      if isinstance(c, Mu):
        child_match = yield from c._find_all_text(pred, traversable)
        if child_match:
          found_match = True
        elif pred(c):
          found_match = True
          yield (c.subnode(self) if traversable else c)
    return found_match


  @overload
  def pick_first(self, type_or_tag:Type[_Mu], *, cl:str='', text:str='', traversable=False, **attrs:str) -> _Mu: ...

  @overload
  def pick_first(self, type_or_tag:str='', *, cl:str='', text:str='', traversable=False, **attrs:str) -> 'Mu': ...

  def pick_first(self, type_or_tag='', *, cl:str='', text:str='', traversable=False, **attrs:str):
    pred = xml_pred(type_or_tag=type_or_tag, cl=cl, text=text, attrs=attrs)
    for c in self._:
      if isinstance(c, Mu) and pred(c): return (c.subnode(self) if traversable else c)
    raise NoMatchError(self, fmt_xml_predicate_args(type_or_tag, cl, text, attrs))


  @overload
  def find_first(self, type_or_tag:Type[_Mu], *, cl:str='', text:str='', traversable=False, **attrs:str) -> _Mu: ...

  @overload
  def find_first(self, type_or_tag:str='', *, cl:str='', text:str='', traversable=False, **attrs:str) -> 'Mu': ...

  def find_first(self, type_or_tag='', *, cl:str='', text:str='', traversable=False, **attrs:str):
    for c in self.find_all(type_or_tag=type_or_tag, cl=cl, text=text, traversable=traversable, **attrs):
      return c
    raise NoMatchError(self, fmt_xml_predicate_args(type_or_tag, cl, text, attrs))


  @overload
  def pick(self, type_or_tag:Type[_Mu], *, cl:str='', text:str='', traversable=False, **attrs:str) -> _Mu: ...

  @overload
  def pick(self, type_or_tag:str='', *, cl:str='', text:str='', traversable=False, **attrs:str) -> 'Mu': ...

  def pick(self, type_or_tag='', *, cl:str='', text:str='', traversable=False, **attrs:str):
    '''
    Pick the matching child of this node.
    Raises NoMatchError if no matching node is found, and MultipleMatchesError if multiple matching nodes are found.
    '''
    first_match:Optional[Mu] = None
    for c in self.pick_all(type_or_tag=type_or_tag, cl=cl, text=text, traversable=traversable, **attrs):
      if first_match is None: first_match = c
      else:
        args_msg = fmt_xml_predicate_args(type_or_tag, cl, text, attrs)
        subsequent_match = c # Alias improves readablity of the following line in stack traces.
        raise MultipleMatchesError(self, args_msg, first_match, subsequent_match)
    if first_match is None:
      raise NoMatchError(self, fmt_xml_predicate_args(type_or_tag, cl, text, attrs))
    return first_match


  @overload
  def find(self, type_or_tag:Type[_Mu], *, cl:str='', text:str='', traversable=False, **attrs:str) -> _Mu: ...

  @overload
  def find(self, type_or_tag:str='', *, cl:str='', text:str='', traversable=False, **attrs:str) -> 'Mu': ...

  def find(self, type_or_tag='', *, cl:str='', text:str='', traversable=False, **attrs:str):
    '''
    Find the matching node of this node's subtree.
    Raises NoMatchError if no matching node is found, and MultipleMatchesError if multiple matching nodes are found.
    '''
    first_match:Optional[Mu] = None
    for c in self.find_all(type_or_tag=type_or_tag, cl=cl, text=text, traversable=traversable, **attrs):
      if first_match is None: first_match = c
      else:
        args_msg = fmt_xml_predicate_args(type_or_tag, cl, text, attrs)
        subsequent_match = c # Alias improves readablity of the following line in stack traces.
        raise MultipleMatchesError(self, args_msg, first_match, subsequent_match)
    if first_match is None:
      raise NoMatchError(self, fmt_xml_predicate_args(type_or_tag, cl, text, attrs))
    return first_match


  # Traversal.

  @overload
  def next(self, type_or_tag:Type[_Mu], *, cl:str='', text:str='', traversable=False, **attrs:str) -> _Mu: ...

  @overload
  def next(self, type_or_tag:str='', *, cl:str='', text:str='', traversable=False, **attrs:str) -> 'Mu': ...

  def next(self, type_or_tag='', *, cl:str='', text:str='', traversable=False, **attrs:str):
    if self._orig is None or self._parent is None: raise ValueError(f'cannot traverse non-subnode: {self}')
    pred = xml_pred(type_or_tag=type_or_tag, cl=cl, text=text, attrs=attrs)
    found_orig = False
    for c in self._parent._:
      if not isinstance(c, Mu): continue
      if found_orig:
        if pred(c): return (c.subnode(self._parent) if traversable else c)
      elif c is self._orig:
        found_orig = True
    if not found_orig: raise ValueError('node was removed from parent')
    raise NoMatchError(self, fmt_xml_predicate_args(type_or_tag, cl, text, attrs))


  @overload
  def prev(self, type_or_tag:Type[_Mu], *, cl:str='', text:str='', traversable=False, **attrs:str) -> _Mu: ...

  @overload
  def prev(self, type_or_tag:str='', *, cl:str='', text:str='', traversable=False, **attrs:str) -> 'Mu': ...

  def prev(self, type_or_tag='', *, cl:str='', text:str='', traversable=False, **attrs:str):
    if self._orig is None or self._parent is None: raise ValueError(f'cannot traverse non-subnode: {self}')
    pred = xml_pred(type_or_tag=type_or_tag, cl=cl, text=text, attrs=attrs)
    found_orig = False
    for c in reversed(self._parent._):
      if not isinstance(c, Mu): continue
      if found_orig:
        if pred(c): return (c.subnode(self._parent) if traversable else c)
      elif c is self._orig:
        found_orig = True
    if not found_orig: raise ValueError('node was removed from parent')
    raise NoMatchError(self, fmt_xml_predicate_args(type_or_tag, cl, text, attrs))


  # Text.

  def summary_texts(self, _needs_space:bool=True) -> Generator[str,None,bool]:
    for child in self._:
      if isinstance(child, Mu):
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

  def summarize(self, levels=1, indent=0, all_attrs=True) -> str:
    nl_indent = '\n' + '  ' * indent
    return ''.join(self._summarize(levels, nl_indent, all_attrs=all_attrs))

  def _summarize(self, levels:int, nl_indent:str, all_attrs:bool) -> Iterator[str]:
    if levels == 0:
      yield str(self)
    else:
      subnode = '' if self._orig is None else '$'
      attr_words = ''.join(xml_attr_summary(k, v, text_limit=32, all_attrs=all_attrs) for k, v in self.attrs.items())
      nl_indent1 = nl_indent + '  '
      yield f'<{subnode}{self.tag}:{attr_words}'
      for c in self._:
        yield nl_indent1
        if isinstance(c, Mu):
          yield from c._summarize(levels-1, nl_indent1, all_attrs)
        else:
          yield repr(c)
      yield '>'


  def discard(self, attr:str) -> None:
    try: del self.attrs[attr]
    except KeyError: pass


  def visit(self, *, pre:MuVisitor|None=None, post:MuVisitor|None=None, traversable=False) -> None:
    if pre is not None: pre(self)

    modified_children:List[MuChild] = []
    first_mod_idx:Optional[int] = None
    for i, c in enumerate(self._):
      if isinstance(c, Mu):
        if traversable: c = c.subnode(self)
        try: c.visit(pre=pre, post=post, traversable=traversable)
        except DeleteNode:
          if first_mod_idx is None: first_mod_idx = i
          continue
        except FlattenNode:
          if first_mod_idx is None: first_mod_idx = i
          modified_children.extend(c._) # Insert children in place of `c`.
          continue
      if first_mod_idx is not None:
        modified_children.append(c)
    if first_mod_idx is not None:
      self._[first_mod_idx:] = modified_children

    if post is not None: post(self)


  def iter_visit(self, *, pre:MuIterVisitor|None=None, post:MuIterVisitor|None=None, traversable=False) -> Iterator[_T]:
    if pre is not None: yield from pre(self)

    for i, c in enumerate(self._):
      if isinstance(c, Mu):
        if traversable: c = c.subnode(self)
        yield from c.iter_visit(pre=pre, post=post, traversable=traversable)

    if post is not None: yield from post(self)


  # Rendering.

  @staticmethod
  def esc_text(text:str) -> str:
    text = text.replace("&", "&amp;") # Ampersand must be replaced first, because escapes use ampersands.
    text = text.replace("<", "&lt;")
    # Note: we do not replace ">" because it is not required and helpful to leave unescaped for embedded CSS.
    return text


  @staticmethod
  def quote_attr_val(text:str) -> str:
    text = text.replace("&", "&amp;") # Ampersand must be replaced first, because escapes use ampersands.
    text = text.replace("<", "&lt;")
    # Note: we do not replace ">" because it is not required and helpful to leave unescaped for inline CSS.
    if "'" in text:
      text = text.replace('"', "&quot;")
      return f'"{text}"'
    else:
      return f"'{text}'"


  def fmt_attr_items(self, items:Iterable[Tuple[str,Any]]) -> str:
    'Return a string that is either empty or with a leading space, containing all of the formatted items.'
    parts: List[str] = []
    for k, v in sorted(items, key=lambda item: self.attr_sort_ranks.get(item[0], 0)):
      k = self.replaced_attrs.get(k, k)
      if v in (None, True, False): v = str(v).lower() # TODO: look up values in a dict for speed?
      elif isinstance(v, Present):
        if v.is_present: v = ''
        else: continue
      parts.append(f" {k}={self.quote_attr_val(str(prefer_int(v)))}")
    return ''.join(parts)


  def render(self, newline=True) -> Iterator[str]:
    'Render the tree as a stream of text lines.'
    yield from self._render()
    if newline: yield '\n'


  def _render(self) -> Iterator[str]:
    'Recursive helper to `render`.'

    if self.void_tags:
      self_closing = self.tag in self.void_tags
      if self_closing and self._: raise ValueError(self)
    else:
      self_closing = not self._

    attrs_str = self.fmt_attr_items(self.attrs.items())
    head_slash = '/' if self_closing else ''
    yield f'<{self.tag}{attrs_str}{head_slash}>'
    if self_closing: return

    yield from self.render_children()
    yield f'</{self.tag}>'


  def render_children(self) -> Iterator[str]:
    child_newlines = (
      len(self._) > 1 and
      (self.tag not in self.ws_sensitive_tags) and
      (self.tag not in self.inline_tags))

    def is_block(el:MuChild) -> bool: return isinstance(el, Mu) and (el.tag not in self.inline_tags)

    if child_newlines:
      yield '\n'
    for child, next_child in window_pairs(self._):
      if isinstance(child, str):
        yield self.esc_text(child)
      elif isinstance(child, Mu):
        yield from child._render()
      elif isinstance(child, EscapedStr):
        assert isinstance(child.string, str), child.string
        yield child.string
      else:
        raise TypeError(child) # Expected str, EscapedStr, or Mu.
      if child_newlines and (is_block(child) or next_child is None or is_block(next_child)):
        yield '\n'


  @staticmethod
  def render_child(child:MuChildLax) -> str:
    if isinstance(child, str): return Mu.esc_text(child)
    if isinstance(child, Mu): return child.render_str()
    if isinstance(child, EscapedStr): return child.string
    if isinstance(child, _mu_child_classes_lax_converted): return Mu.esc_text(str(child))
    else: raise TypeError(child)


  def render_str(self, newline=True) -> str:
    'Render the tree into a single string.'
    return ''.join(self.render(newline=newline))


  def render_children_str(self, newline=True) -> str:
    'Render the children into a single string.'
    return ''.join(self.render_children())


Mu.generic_tag_type = Mu # Note: this creates a circular reference.


mu_child_classes = (str, EscapedStr, Mu)
_mu_child_classes_lax_converted = (int, float, bool, type(None))
mu_child_classes_lax = mu_child_classes + _mu_child_classes_lax_converted


def xml_attr_summary(key:str, val:Any, *, text_limit:int, all_attrs:bool) -> str:
  ks = key if _word_re.fullmatch(key) else repr(key)
  if all_attrs or key in ('id', 'class'): return f' {ks}={repr_lim(val, text_limit)}' # Show id and class values.
  return f' {ks}=…' # Omit other attribute values.


def xml_child_summary(child:MuChild, text_limit:int) -> str:
  if isinstance(child, Mu):
    text = child.summary_text(limit=text_limit)
    if text: return f' {child.tag}:{repr_lim(text, limit=text_limit)}'
    return ' ' + child.tag
  if isinstance(child, EscapedStr):
    child = child.string
  text = html_ws_re.sub(newline_or_space_for_ws, child)
  return ' ' + repr_lim(text, limit=text_limit)


def xml_pred(type_or_tag:Union[str,Type[_Mu]]='', *, cl:str='', text:str='', attrs:Dict[str,Any]={}) -> MuPred:
  'Update _attrs with items from other arguments, then construct a predicate that tests Mu nodes.'

  tag_pred:Callable
  if not type_or_tag: tag_pred = lambda node: True
  elif isinstance(type_or_tag, type): tag_pred = lambda node: isinstance(node, type_or_tag) # type: ignore[arg-type]
  else: tag_pred = lambda node: node.tag == type_or_tag

  def predicate(node:Mu) -> bool:
    return (
      tag_pred(node) and
      (not cl or cl in node.classes) and
      all(node.attrs.get(k.replace('_', '-')) == v for k, v in attrs.items()) and
      (not text or text in node.text))

  return predicate


def fmt_xml_predicate_args(type_or_tag:Union[Type,str], cl:str, text:str, attrs:Dict[str,str]) -> str:
  'Format the arguments of a predicate function for an error message.'
  words:List[str] = []
  if type_or_tag: words.append(f'`{type_or_tag.__name__}`' if isinstance(type_or_tag, type) else repr(type_or_tag))
  if cl: words.append(f'cl={cl!r}')
  for k, v in attrs.items(): words.append(xml_attr_summary(k, v, text_limit=0, all_attrs=True).lstrip())
  if text: words.append(f'…{text!r}…')
  return ' '.join(words)


def add_opt_attrs(attrs:Dict[str,Any], **items:Any) -> None:
  'Add the items in `**items` attrs, excluding any None values.'
  for k, v in items.items():
    if v is None: continue
    assert k not in attrs, k
    attrs[k] = v


_Child = TypeVar('_Child', bound=Mu)
_Self = TypeVar('_Self', bound=Mu)

def single_child_property(constructor:Callable[[_Self],_Child]) -> property:
  '''
  Decorator for creating single-child-of-class properties.
  For example, the Html package uses this to define Html.head, Html.body, Body.main, etc.
  The decorated property must be annotated with the child class return type (possibly as a string for forward references),
  and should be implemented using `return ChildClass()` or similar.
  '''

  ann = get_annotations(constructor, eval_str=False)
  ret = ann['return']
  class_desc = ret if isinstance(ret, str) else ret.__name__

  _child_class:type[_Child]|None = ret if isinstance(ret, type) else None

  def get_child_class() -> type[_Child]:
    nonlocal _child_class
    if _child_class is None:
      ann = get_annotations(constructor, eval_str=True)
      ret = ann['return']
      assert issubclass(ret, Mu), ret
      _child_class = ret
    return cast(type[_Child], _child_class)

  @wraps(constructor)
  def _get_single_child_prop(self:_Self) -> _Child:
    child_class = get_child_class()
    for c in self._:
      if isinstance(c, child_class): return c
    return self.append(constructor(self))

  def _set_single_child_prop(self:_Self, val:_Child) -> None:
    child_class = get_child_class()
    for i, c in enumerate(self._):
      if isinstance(c, child_class):
        self._[i] = val
        return
    self.append(val)

  def _del_single_child_prop(self:_Self) -> None:
    child_class = get_child_class()
    for i, c in enumerate(self._):
      if isinstance(c, child_class):
        del self._[i]
        return

  doc = f'The single child element of type {class_desc}.\n' + (constructor.__doc__ or '')
  return property(_get_single_child_prop, _set_single_child_prop, _del_single_child_prop, doc=doc)



@overload
def prefer_int(v:int) -> int: ...
@overload
def prefer_int(v:float) -> Union[int,float]: ...
@overload
def prefer_int(v:str) -> str: ...

def prefer_int(v:Union[float,int,str]) -> Union[float,int,str]:
  'Convert integral floats to int.'
  if isinstance(v, float):
    i = int(v)
    return i if i == v else v
  return v


def newline_or_space_for_ws(match:Match) -> str:
  'Collapse whitespace to either a newline or single space.'
  return '\n' if '\n' in match[0] else ' '


# HTML defines ASCII whitespace as "U+0009 TAB, U+000A LF, U+000C FF, U+000D CR, or U+0020 SPACE."
html_ws_re = re.compile(r'[\t\n\f\r ]+')
html_ws_split_re = re.compile(r'(?P<space>[\t\n\f\r ])|[^\t\n\f\r ]+')

_word_re = re.compile(r'[-\w]+')
