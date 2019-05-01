# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
XML tools.
'''

from enum import Enum
from io import StringIO
from itertools import chain, count
from types import TracebackType
from typing import Any, ContextManager, Dict, Iterable, Iterator, List, Optional, Sequence, TextIO, Tuple, Type, TypeVar, Union

from ..io import errSL
from ..typing import OptBaseExc, OptTraceback, OptTypeBaseExc

from .escape import EscapedStr, XmlAttrs, esc_xml_attr, esc_xml_attr_key, esc_xml_text, fmt_attrs


_XmlWriter = TypeVar('_XmlWriter', bound='XmlWriter')


class IndexCounters:
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
    'cl' : 'class',
  }

  can_auto_close_tags = True # Allows treating all elements as "void" or "self-closing", e.g. '<TAG/>'. False for HTML.
  is_self_closing = False # True for e.g. HTML tags that are self closing, such as <img />.
  tag:str = '' # Subclasses can specify a tag.

  def __init__(self, *_children:Any, tag:str=None, _counters:IndexCounters=None, attrs:XmlAttrs=None, **kwargs:Any) -> None:
    '''
    `attrs` also allows for XML attributes that contain non-identifier characters.
    '''
    self.tag = tag or type(self).tag
    if not self.tag: raise Exception(f'{type(self)}: neither type-level tag nor constructor tag specified')
    self.prefix = ''
    self.children = list(_children)
    self.inline:Optional[bool] = None
    self.attrs = kwargs # Guaranteed not to be referenced anywhere else, whereas attrs might be.
    if attrs: self.attrs.update(attrs)
    self._appears_inline = bool(self.children)
    self._context_depth = 0
    self._is_closed = False
    self._counters:IndexCounters = _counters or IndexCounters()


  def write(self, file:TextIO, end='\n') -> None:
    if self.prefix: print(self.prefix, file=file)
    print('<', self.tag, fmt_attrs(self.attrs, self.replaced_attrs), sep='', end='', file=file)
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

  def __exit__(self, exc_type:OptTypeBaseExc, exc_value:OptBaseExc, traceback:OptTraceback) -> None:
    self._context_depth -= 1
    if self._context_depth == 0:
      self._is_closed = True
      self.on_close()


  def on_close(self) -> None:
    'Optional closing action for subclasses.'


  def add(self, *items:Any, sep='', end='\n') -> None:
    if self._is_closed: raise Exception(f'XmlWriter is already closed: {self}')
    self.children.extend(items)


  def leaf(self, tag:str, *, attrs:XmlAttrs) -> None:
    self.add(EscapedStr(f'<{tag}{fmt_attrs(attrs, self.replaced_attrs)}/>'))


  def child(self, child_class:Type[_XmlWriter], *children:Any, attrs:XmlAttrs=None, **kwargs:Any) -> _XmlWriter:
    'Create a child XmlWriter for use in a `with` context to represent a nesting XML element.'
    if self._is_closed: raise Exception(f'XmlWriter is already closed: {self}')
    c = child_class(*children, _counters=self._counters, attrs=attrs, **kwargs)
    self.add(c)
    return c


  def gen_id(self) -> str:
    return f'_id{next(self._counters.id_counter)}'

  def gen_class(self) -> str:
    return f'_class{next(self._counters.class_counter)}'


def add_opt_attrs(attrs:Dict[str,Any], *pairs:Tuple[str, Any], **items:Any) -> None:
  'Add the items in `*pairs` and `**items` attrs, excluding any None values.'
  for k, v in chain(pairs, items.items()):
    if v is None: continue
    assert k not in attrs, k
    attrs[k] = v
