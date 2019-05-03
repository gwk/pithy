# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
XML selector.
'''

import re
from typing import Any, Callable, Dict, Generator, Iterator, List, Optional, Tuple, Union, cast

from ..desc import repr_lim
from ..exceptions import MultipleMatchesError, NoMatchError
from . import Xml, XmlKey, XmlChild


XmlChildSel = Union[str,'XmlSel']


class XmlSel:

  def __init__(self, node:Xml, idx:int=None, back:'XmlSel'=None) -> None:
    'Create an XmlSel selector for the given Xml node.'
    self.node = node
    self.idx = idx
    self.back = back


  def __repr__(self) -> str:
    words = ' '.join(_item_summary(k, v) for k, v in self.node.items())
    return f'<{words}>'


  def __iter__(self) -> Iterator[XmlChild]:
    'Iteration yields the node text and child element values, without selector wrappers.'
    return self.node.children


  def __getitem__(self, sel:Union[int,str]) -> XmlChildSel:
    '''
    Get the item whose key (attribute name or numeric index) is `sel`,
    or else the child node with matching tag, id, or class.
    Raises MultipleMatchesError when multiple child nodes match.
    '''
    # First attempt direct access of underlying dict.
    try: v = self.node[sel]
    except KeyError: pass
    else:
      if isinstance(v, Xml):
        assert isinstance(sel, int)
        return XmlSel(v, idx=sel, back=self)
      else:
        return v

    # Select all matching children.
    pairs = [(k,v) for (k,v) in self.node.items() if isinstance(k, int) and isinstance(v, dict)
      and (v.get(None) == sel or v.get('id') == sel or v.get('class') == sel)]
    if not pairs: raise NoMatchError(sel)
    if len(pairs) > 1: raise MultipleMatchesError(pairs)
    k, v = pairs[0]
    return XmlSel(v, idx=k, back=self)


  def __getattr__(self, sel:str) -> XmlChildSel:
    'Dot-syntax alias for item access.'
    return self[sel]


  @property
  def sels(self) -> List['XmlSel']:
    return [XmlSel(v, idx=k, back=self) for k, v in self.node.items() if isinstance(k, int) and isinstance(v, Xml)]


  @property
  def tag(self) -> str: return self.node.tag


  def get(self, sel:Union[int,str], default:XmlChildSel=None) -> Optional[XmlChildSel]:
    try: return self[sel]
    except KeyError: return default


  def  _mk_predicate(self, sel:Optional[str], tag:Optional[str], cl:Optional[str], text:Optional[str],
   attrs:Dict[str,str], _attrs:Dict[str,str]) -> Callable[[Xml],bool]:
    'Update _attrs with items from other arguments, then construct a predicate that tests Xml nodes.'


    def add(k:str, v:str) -> None:
      if _attrs.get(k, v) != v: raise ValueError('conflicting selectors for {k!r}: {v!r} != {_attrs[k]!r}')
      _attrs[k] = v

    if sel is not None:
      if not sel: raise ValueError('`sel` should not be empty string')
    if tag is not None: # Test for tag handled specially due to None key.
      if not tag: raise ValueError('`tag` should not be empty string')
      add(None, tag) # type: ignore # Special exception for the tag's None key.
    if cl is not None: # Test for 'class' handled specially due to rename.
      add('class', cl)
    for k, v in attrs.items():
      add(k, v)

    def predicate(node:Xml) -> bool:
      return (
        (not sel or node.get(None) == sel or node.get('id') == sel or node.get('class') == sel) and
        all(node.get(ak) == av for ak, av in _attrs.items()) and
        (not text or bool(re.search(text, node.text))))

    return predicate


  def all(self, sel:str=None, tag:str=None, cl:str=None, text:str=None,
   attrs:Dict[str,str]={}, **_attrs:str) -> Iterator['XmlSel']:
    pred = self._mk_predicate(sel=sel, tag=tag, cl=cl, text=text, attrs=attrs, _attrs=_attrs)
    for k, v in self.node.items():
      if not (isinstance(k, int) and isinstance(v, dict)): continue
      if pred(v):
        yield XmlSel(v, idx=k, back=self)

  def _find_all(self, pred:Callable[[Xml],bool]) -> Iterator['XmlSel']:
    for k, v in self.node.items():
      if not (isinstance(k, int) and isinstance(v, dict)): continue
      c = XmlSel(v, idx=k, back=self)
      if pred(v):
        yield c
      else:
        yield from c._find_all(pred)

  def find_all(self, sel:str=None, tag:str=None, cl:str=None, text:str=None,
   attrs:Dict[str,str]={}, **_attrs:str) -> Iterator['XmlSel']:
    pred = self._mk_predicate(sel=sel, tag=tag, cl=cl, text=text, attrs=attrs, _attrs=_attrs)
    return self._find_all(pred=pred)

  def first(self, sel:str=None, tag:str=None, cl:str=None, text:str=None,
   attrs:Dict[str,str]={}, **_attrs:str) -> 'XmlSel':
    try: return next(self.all(sel=sel, tag=tag, cl=cl, text=text, attrs=attrs, **_attrs))
    except StopIteration: pass
    raise NoMatchError(f'sel={sel!r}, tag={tag!r}, cl={cl!r}, text={text!r}, attrs={attrs}, **{_attrs}; node={self}')

  def find(self, sel:str=None, tag:str=None, cl:str=None, text:str=None,
   attrs:Dict[str,str]={}, **_attrs:str) -> 'XmlSel':
    try: return next(self.find_all(sel=sel, tag=tag, cl=cl, text=text, attrs=attrs, **_attrs))
    except StopIteration: pass
    raise NoMatchError(f'sel={sel!r}, tag={tag!r}, cl={cl!r}, text={text!r}, attrs={attrs}, **{_attrs}; node={self}')

  # TODO: find_first?

  # Traversal.

  def traverse(self, distance:int, sel:str=None, tag:str=None, cl:str=None, text:str=None,
   attrs:Dict[str,str]={}, **_attrs:str) -> XmlChildSel:
    if self.idx is None or self.back is None: raise ValueError('cannot traverse root XmlSel')
    assert distance != 0
    i = self.idx + distance
    s = self.back[i]
    if sel is None and tag is None and cl is None and not attrs: return s
    # Continue traversing until we find a matching element.
    step = 1 if distance > 0 else -1
    pred = self._mk_predicate(sel=sel, tag=tag, cl=cl, text=text, attrs=attrs, _attrs=_attrs)
    while not (isinstance(s, XmlSel) and pred(s.node)):
      i += step
      s = self.back[i]
    assert s.idx and s.back, s
    return s

  def prev(self, sel:str=None, tag:str=None, cl:str=None, text:str=None,
   attrs:Dict[str,str]={}, **_attrs:str) -> XmlChildSel:
    return self.traverse(distance=-1, sel=sel, tag=tag, cl=cl, text=text, attrs=attrs, **_attrs)

  def next(self, sel:str=None, tag:str=None, cl:str=None, text:str=None,
   attrs:Dict[str,str]={}, **_attrs:str) -> XmlChildSel:
    return self.traverse(distance=1, sel=sel, tag=tag, cl=cl, text=text, attrs=attrs, **_attrs)


  # Text extraction.

  def all_texts(self, exact=False, _needs_space:bool=True) -> Generator[str,None,bool]:
    for c in self:
      if isinstance(c, dict):
        _needs_space = yield from XmlSel(c).all_texts(exact=exact, _needs_space=_needs_space)
        continue
      raw = str(c)
      if exact:
        yield raw
        continue
      for m in _ws_split_re.finditer(raw):
        if m.lastgroup == 'space':
          if _needs_space:
            yield ' '
            _needs_space = False
        else:
          yield m[0]
          _needs_space = True
    return _needs_space

  def text(self, exact=False, limit=0) -> str:
    if not limit: return ''.join(self.all_texts(exact=exact))
    parts:List[str] = []
    length = 0
    for part in self.all_texts(exact=exact):
      parts.append(part)
      length += len(part)
      if length > limit: break
    return ''.join(parts)[:limit]

  # Text summary.

  def summarize(self, levels=1, indent=0) -> str:
    ni = '\n' + '  ' * indent
    return ''.join(self._summarize(levels, ni))

  def _summarize(self, levels:int, ni:str) -> Iterator[str]:
    if levels <= 0:
      words = ' '.join(_item_summary(k, v) for k, v in self.node.items())
      yield f'<{words}>'
      return
    else:
      yield '<'
      yield self.tag
      ni1 = ni + '  '
      for k, v in self.node.items():
        if isinstance(k, str):
          yield ' '
          yield k
          yield '='
          yield repr(v)
        else:
          yield ni1
          if not isinstance(v, dict):
            yield repr(v)
          else:
            yield from XmlSel(v)._summarize(levels-1, ni1)



def _item_summary(key:XmlKey, val:XmlChild, text_limit=32) -> str:
  if key is None: return f'{val}:' # Tag is stored under None.
  if isinstance(key, str):
    if key in ('id', 'class'): return f'{key}={val!r}' # Show id and class values.
    return f'{key}=…' # Omit other attribute values.
  if isinstance(val, dict):
    try:
      sel = XmlSel(val)
      t = sel.text(exact=True, limit=text_limit)
      return f'{sel.tag}:{repr_lim(t, limit=text_limit)}'
    except KeyError: pass
  return repr_lim(val, limit=text_limit)


# HTML defines ASCII whitespace as "U+0009 TAB, U+000A LF, U+000C FF, U+000D CR, or U+0020 SPACE."
_ws_split_re = re.compile(r'(?P<space>[\t\n\f\r ])|[^\t\n\f\r ]+')
