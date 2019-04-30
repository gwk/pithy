# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
XML selector.
'''

import re
from typing import Any, Callable, Dict, Generator, Iterator, List, Optional, Tuple, Union, cast

from ..desc import repr_lim


_XmlKey = Union[int,str]
_XmlChild = Union[str,dict]
_XmlDict = Dict[_XmlKey,_XmlChild]
_XmlChildSel = Union[str,'XmlSel']


class MultipleMatchesError(KeyError):
  'Raised when a query matches multiple children.'

class NoMatchError(KeyError):
  'Raised when a query matches no children.'


class XmlSel:

  def __init__(self, dict:_XmlDict, idx:int=None, back:'XmlSel'=None) -> None:
    'Create an XmlSelector from a dictionary, which should have been built from parsed XML.'
    self.dict = dict
    self.idx = idx
    self.back = back


  def __repr__(self) -> str:
    words = ' '.join(_item_summary(k, v) for k, v in self.dict.items())
    return f'<{words}>'

  def __iter__(self) -> Iterator[_XmlChild]:
    'Iteration yields the raw text and child node values, without selector wrappers.'
    for k, v in self.dict.items():
      if isinstance(k, int):
        yield v

  @property
  def texts(self) -> List[str]:
    return [c for c in self if isinstance(c, str)]

  @property
  def nodes(self) -> List[_XmlDict]:
    return [c for c in self if isinstance(c, dict)]

  @property
  def sels(self) -> List['XmlSel']:
    return [XmlSel(v, idx=k, back=self) for k, v in self.dict.items() if isinstance(k, int) and isinstance(v, dict)]

  @property
  def tag(self) -> str: return cast(str, self.dict[''])

  @property
  def cl(self) -> Optional[str]:
    try: c = self.dict['class']
    except KeyError: return None
    assert isinstance(c, str)
    return c

  @property
  def attrs(self) -> Dict[str,str]:
    # Note: we actually call `str` on `v` instead of casting to increase stability,
    # at the expense of possibly masking erroneous input data.
    return {k: str(v) for (k, v) in self.dict.items() if isinstance(k, str)}


  def __getitem__(self, sel:Union[int,str]) -> _XmlChildSel:
    '''
    Get the item whose key (attribute name or numeric index) is `sel`,
    or else the child node with matching tag, id, or class.
    Raises MultipleMatchesError when multiple child nodes match.
    '''
    if isinstance(sel, str): return cast(str, self.dict[sel]) # Attribute access.
    # First attempt direct access of underlying dict.
    try: v = self.dict[sel]
    except KeyError: pass
    else: return XmlSel(v, idx=sel, back=self) if isinstance(v, dict) else v

    # Select all matching children.
    pairs = [(k,v) for (k,v) in self.dict.items() if isinstance(k, int) and isinstance(v, dict)
      and (v.get('') == sel or v.get('id') == sel or v.get('class') == sel)]
    if not pairs: raise NoMatchError(sel)
    if len(pairs) > 1: raise MultipleMatchesError(pairs)
    k, v = pairs[0]
    return XmlSel(v, idx=k, back=self)


  def __getattr__(self, sel:str) -> _XmlChildSel:
    'Dot-syntax alias for item access.'
    return self[sel]

  def get(self, sel:Union[int,str], default:_XmlChildSel=None) -> Optional[_XmlChildSel]:
    try: return self[sel]
    except KeyError: return default


  def  _mk_predicate(self, sel:Optional[str], tag:Optional[str], cl:Optional[str], text:Optional[str],
   attrs:Dict[str,str], _attrs:Dict[str,str]) -> Callable[[_XmlDict],bool]:
    'Update _attrs with items from other arguments, then construct a predicate that tests dicts.'

    def add(k:str, v:str) -> None:
      if _attrs.get(k, v) != v: raise ValueError('conflicting selectors for {k!r}: {v!r} != {_attrs[k]!r}')
      _attrs[k] = v

    if sel is not None:
      if not sel: raise ValueError('`sel` should not be empty string')
    if tag is not None:
      if not tag: raise ValueError('`tag` should not be empty string')
      add('', tag)
    if cl is not None:
      add('class', cl)
    for k, v in attrs.items():
      add(k, v)

    def predicate(d:_XmlDict) -> bool:
      return (
        (not sel or d.get('') == sel or d.get('id') == sel or d.get('class') == sel) and
        all(d.get(ak) == av for ak, av in _attrs.items()) and
        (not text or bool(re.search(text, XmlSel(d).text()))))

    return predicate


  def all(self, sel:str=None, tag:str=None, cl:str=None, text:str=None,
   attrs:Dict[str,str]={}, **_attrs:str) -> Iterator['XmlSel']:
    pred = self._mk_predicate(sel=sel, tag=tag, cl=cl, text=text, attrs=attrs, _attrs=_attrs)
    for k, v in self.dict.items():
      if not (isinstance(k, int) and isinstance(v, dict)): continue
      if pred(v):
        yield XmlSel(v, idx=k, back=self)

  def _find_all(self, pred:Callable[[_XmlDict],bool]) -> Iterator['XmlSel']:
    for k, v in self.dict.items():
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
    raise NoMatchError(f'sel={sel!r}, tag={tag!r}, cl={cl!r}, text={text!r}, attrs={attrs}, **{_attrs}')

  def find(self, sel:str=None, tag:str=None, cl:str=None, text:str=None,
   attrs:Dict[str,str]={}, **_attrs:str) -> 'XmlSel':
    try: return next(self.find_all(sel=sel, tag=tag, cl=cl, text=text, attrs=attrs, **_attrs))
    except StopIteration: pass
    raise NoMatchError(f'sel={sel!r}, tag={tag!r}, cl={cl!r}, text={text!r}, attrs={attrs}, **{_attrs}')

  # TODO: find_first?

  # Traversal.

  def traverse(self, distance:int, sel:str=None, tag:str=None, cl:str=None, text:str=None,
   attrs:Dict[str,str]={}, **_attrs:str) -> _XmlChildSel:
    if self.idx is None or self.back is None: raise ValueError('cannot traverse root XmlSel')
    assert distance != 0
    i = self.idx + distance
    s = self.back[i]
    if sel is None and tag is None and cl is None and not attrs: return s
    # Continue traversing until we find a matching element.
    step = 1 if distance > 0 else -1
    pred = self._mk_predicate(sel=sel, tag=tag, cl=cl, text=text, attrs=attrs, _attrs=_attrs)
    while not (isinstance(s, XmlSel) and pred(s.dict)):
      i += step
      s = self.back[i]
    assert s.idx and s.back, s
    return s

  def prev(self, sel:str=None, tag:str=None, cl:str=None, text:str=None,
   attrs:Dict[str,str]={}, **_attrs:str) -> _XmlChildSel:
    return self.traverse(distance=-1, sel=sel, tag=tag, cl=cl, text=text, attrs=attrs, **_attrs)

  def next(self, sel:str=None, tag:str=None, cl:str=None, text:str=None,
   attrs:Dict[str,str]={}, **_attrs:str) -> _XmlChildSel:
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
      words = ' '.join(_item_summary(k, v) for k, v in self.dict.items())
      yield f'<{words}>'
      return
    else:
      yield '<'
      yield self.tag
      ni1 = ni + '  '
      for k, v in self.dict.items():
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



def _item_summary(key:_XmlKey, val:_XmlChild, text_limit=32) -> str:
  if isinstance(key, str):
    if not key: return f'{val}:' # Tag is stored under empty key.
    if key in ('id', 'class'): return f'{key}={val!r}' # Show id and class values.
    return f'{key}=' # Omit other attribute values.
  if isinstance(val, dict):
    try:
      sel = XmlSel(val)
      t = sel.text(exact=True, limit=text_limit)
      return f'{sel.tag}{repr_lim(t, limit=text_limit)}'
    except KeyError: pass
  return repr_lim(val, limit=text_limit)

# HTML defines ASCII whitespace as "U+0009 TAB, U+000A LF, U+000C FF, U+000D CR, or U+0020 SPACE."
_ws_split_re = re.compile(r'(?P<space>[\t\n\f\r ])|[^\t\n\f\r ]+')
