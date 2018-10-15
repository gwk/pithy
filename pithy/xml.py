# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
XML tools.
'''

from enum import Enum
from html import escape as html_escape
from io import StringIO
from itertools import chain, count
from types import TracebackType
from typing import Any, ContextManager, Dict, Iterable, Iterator, List, Optional, Sequence, TextIO, Tuple, Type, TypeVar, Union
from .io import errSL


_XmlWriter = TypeVar('_XmlWriter', bound='XmlWriter')

XmlAttrs = Optional[Dict[str,Any]]


class EscapedStr(str):
  'A `str` subclass that signifies to some receiver that it has already been properly escaped.'


class _Counter:
  'Internal pair of counters for XmlWriter to generate "id" and "class" attributes.'
  def __init__(self) -> None:
    self.id_counter = count()
    self.class_counter = count()


class XmlWriter(ContextManager):
  '''
  XmlWriter is the root class for building document trees for output.
  XmlWriter is subclassed to provide more convenient Python APIs; see pithy.html and pithy.svg.
  '''

  replaced_attrs = {
    'class_' : 'class',
  }

  can_auto_close_tags = True # Allows treating all elements as "void" or "self-closing", for example '<TAG/>'. False for HTML.
  tag:str = '' # Subclasses can specify a tag.

  def __init__(self, *_children:Any, tag:str=None, _counter:_Counter=None, attrs:XmlAttrs=None, **kwargs:Any) -> None:
    '''
    `attrs` also allows for XML attributes that contain non-identifier characters.
    '''
    self.tag = tag or type(self).tag
    if not self.tag: raise Exception(f'{type(self)}: neither type-level tag nor argument tag specified')
    self.prefix = ''
    self.children = list(_children)
    self.inline:Optional[bool] = None
    self.attrs = kwargs
    if attrs: self.attrs.update(attrs)
    self._appears_inline = bool(self.children)
    self._context_depth = 0
    self._is_closed = False
    self._counter:_Counter = _counter or _Counter()


  def write(self, file:TextIO, end='\n') -> None:
    if self.prefix: print(self.prefix, file=file)
    print('<', self.tag, self.fmt_attrs(self.attrs), sep='', end='', file=file)
    if self.can_auto_close_tags and not self.children:
      print('/>', end=end, file=file)
      return
    inline = self._appears_inline if (self.inline is None) else self.inline
    child_end = ('' if inline else '\n')
    print('>', end=child_end, file=file)
    for child in self.children:
      if isinstance(child, XmlWriter):
        child.write(end=child_end, file=file)
      else:
        print(esc_xml_text(child), end=child_end, file=file)
    print('</', self.tag, '>', sep='', end=end, file=file)


  @property
  def string(self) -> str:
    s = StringIO()
    self.write(file=s)
    return s.getvalue()


  def __repr__(self) -> str:
    return f'{self.__class__.__name__}({self.tag!r})'


  def __enter__(self:_XmlWriter) -> _XmlWriter:
    if self._is_closed: raise Exception(f'XmlWriter is already closed: {self}')
    self._context_depth += 1
    return self


  def __exit__(self, exc_type:Optional[Type[BaseException]], exc_value:Optional[BaseException],
   traceback: Optional[TracebackType]) -> None:
    self._context_depth -= 1
    if self._context_depth == 0:
      self._is_closed = True


  def add(self, *items:Any, sep='', end='\n') -> None:
    if self._is_closed: raise Exception(f'XmlWriter is already closed: {self}')
    self.children.extend(items)


  def leaf(self, tag:str, *, attrs:XmlAttrs) -> None:
    self.add(EscapedStr(f'<{tag}{self.fmt_attrs(attrs)}/>'))


  def child(self, child_class:Type[_XmlWriter], *children:Any, attrs:XmlAttrs=None, **kwargs:Any) -> _XmlWriter:
    'Create a child XmlWriter for use in a `with` context to represent a nesting XML element.'
    if self._is_closed: raise Exception(f'XmlWriter is already closed: {self}')
    c = child_class(*children, _counter=self._counter, attrs=attrs, **kwargs)
    self.add(c)
    return c


  def fmt_attrs(self, attrs:XmlAttrs) -> str:
    'Format the `attrs` dict into XML key-value attributes.'
    if not attrs: return ''
    parts: List[str] = []
    for k, v in attrs.items():
      if v is None:
        v = 'none'
      else:
        k = self.replaced_attrs.get(k, k)
      parts.append(f' {esc_xml_attr(k.replace("_", "-"))}="{esc_xml_attr(v)}"')
    return ''.join(parts)


  def gen_id(self) -> str:
    return f'_id{next(self._counter.id_counter)}'

  def gen_class(self) -> str:
    return f'_class{next(self._counter.class_counter)}'


def add_opt_attrs(attrs:Dict[str,Any], *pairs:Tuple[str, Any], **items:Any) -> None:
  'Add the items in `*pairs` and `**items` attrs, excluding any None values.'
  for k, v in chain(pairs, items.items()):
    if v is None: continue
    assert k not in attrs, k
    attrs[k] = v


def esc_xml_text(val:Any) -> str:
  'HTML-escape the string representation of `val`.'
  # TODO: add options to support whitespace escaping?
  return val if isinstance(val, EscapedStr) else html_escape(str(val), quote=False)


def esc_xml_attr(val:Any) -> str:
  'HTML-escape the string representation of `val`, including quote characters.'
  return val if isinstance(val, EscapedStr) else html_escape(str(val), quote=True)

