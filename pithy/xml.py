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

_Counter = Iterator[int]

class XmlWriter(ContextManager):
  '''
  XmlWriter is a ContextManager class that outputs XML text to a file (stdout by default).
  It uses the __enter__ and __exit__ methods to automatically output open and close tags.
  XmlWriter can be subclassed to provide convenient Python APIs; see pithy.html and pithy.svg.
  '''

  replaced_attrs = {
    'class_' : 'class',
  }

  can_auto_close_tags = True # Allows "void" or "self-closing" elements, e.g. <TAG />. False for HTML.
  tag:str = '' # Subclasses can specify a tag.

  def __init__(self, *args:Any, children:Iterable[Any]=(), tag:str=None, file:TextIO=None, attrs:XmlAttrs=None,
    _id_counter:_Counter=None, _class_counter:_Counter=None,
   **kwargs:Any) -> None:
    '''
    `children` and `attrs` are provided as named parameters to avoid excessive copying into `args` and `kwargs`.
    `attrs` also allows for XML attributes that contain non-identifier characters.
    '''
    self.file = file or StringIO()
    self.tag = tag or type(self).tag
    if not self.tag: raise Exception(f'{type(self)}: neither type-level tag nor argument tag specified')
    self.context_depth = 0
    self.is_closed = False
    self.open_child:Optional['XmlWriter'] = None
    self._id_counter:_Counter = _id_counter or count()
    self._class_counter:_Counter = _class_counter or count()

    # An Ellipsis indicates that the children should be printed one per line,
    # and that the element should not be immediately closed.
    has_ellipsis = False
    child_strs = []
    for child in chain(children, args):
      if child is Ellipsis:
        has_ellipsis = True
        continue
      if isinstance(child, XmlWriter):
        child.close()
        child_strs.append(child.string.rstrip('\n'))
      else:
        child_strs.append(esc_xml_text(child))

    # If there is the possibility of self-closing the element, then leave the open-tag incomplete.
    self.is_open_tag_incomplete = self.can_auto_close_tags and not (child_strs or has_ellipsis)
    close_now = (child_strs and not has_ellipsis)

    bracket = ('' if self.is_open_tag_incomplete else '>')
    print(f'<{self.tag}{self.fmt_attrs(attrs, kwargs)}{bracket}',
      *child_strs,
      sep=('\n' if has_ellipsis else ''),
      end=('' if self.is_open_tag_incomplete or close_now else '\n'),
      file=self.file)

    if close_now: self.close()


  @property
  def string(self) -> str:
    if not isinstance(self.file, StringIO):
      raise TypeError(f'{self} cannot get string value for non-StringIO backing file: {self.file}')
    return self.file.getvalue()


  def __repr__(self) -> str:
    return f'{self.__class__.__name__}({self.tag!r})'


  def __del__(self:_XmlWriter) -> None:
    if not getattr(self, 'is_closed', True): # If attribute is missing, then __init__ raised and we do not need to warn here.
      errSL('WARNING: XmlWriter was deleted but not closed:', self)


  def __enter__(self:_XmlWriter) -> _XmlWriter:
    if self.is_closed: raise Exception(f'XmlWriter is already closed: {self}')
    self.context_depth += 1
    return self


  def __exit__(self, exc_type:Optional[Type[BaseException]], exc_value:Optional[BaseException],
   traceback: Optional[TracebackType]) -> None:
   self.context_depth -= 1
   if not self.context_depth: self.close()


  def complete_open_tag(self) -> None:
    if self.is_open_tag_incomplete:
      print('>', file=self.file)
      self.is_open_tag_incomplete = False


  def check_open_child(self) -> None:
    if self.open_child is not None:
      if not self.open_child.is_closed: raise Exception(f'{self}: previously opened child {self.open_child} was not closed')
      self.open_child = None


  def close(self) -> None:
    if not self.is_closed:
      self.check_open_child()
      if self.is_open_tag_incomplete: # Self-closing element.
        print('/>', file=self.file)
        self.is_open_tag_incomplete = False
      else:
        print(f'</{self.tag}>', file=self.file)
      self.is_closed = True


  def write_unescaped(self, *items:Any, sep='', end='\n') -> None:
    assert not self.is_closed
    if not items: return
    self.check_open_child()
    self.complete_open_tag()
    print(*items, sep=sep, end=end, file=self.file)


  def write(self, *items:Any, sep='', end='\n') -> None:
    self.write_unescaped(*(esc_xml_text(item) for item in items), sep=sep, end=end)


  def leaf(self, tag:str, *, attrs:XmlAttrs) -> None:
    self.write_unescaped(f'<{tag}{self.fmt_attrs(attrs)}/>')


  def child(self, child_class:Type[_XmlWriter], *args:Any, children:Iterable[Any]=(), tag:str=None, attrs:XmlAttrs=None, **kwargs:Any) -> _XmlWriter:
    'Create a child XmlWriter for use in a `with` context to represent a nesting XML element.'
    assert not self.is_closed
    self.check_open_child()
    self.complete_open_tag()
    self.open_child = child_class(*args, tag=tag, file=self.file, attrs=attrs, children=children,
     _id_counter=self._id_counter, _class_counter=self._class_counter, **kwargs)
    return self.open_child


  def fmt_attrs(self, attrs:XmlAttrs, kwarg_attrs:XmlAttrs=None) -> str:
    'Format the `attrs` dict into XML key-value attributes.'
    if not attrs and not kwarg_attrs: return ''

    items: Iterable[Tuple[str, Any]]
    if attrs and kwarg_attrs: items = chain(attrs.items(), kwarg_attrs.items())
    elif attrs: items = attrs.items()
    else:
      assert kwarg_attrs is not None
      items = kwarg_attrs.items()

    parts: List[str] = []
    for k, v in items:
      if v is None:
        v = 'none'
      else:
        k = self.replaced_attrs.get(k, k)
      parts.append(f' {esc_xml_attr(k.replace("_", "-"))}="{esc_xml_attr(v)}"')
    return ''.join(parts)


  def gen_id(self) -> str:
    if self._id_counter is None:
      self._id_counter = count()
    return f'_id{next(self._id_counter)}'

  def gen_class(self) -> str:
    if self._class_counter is None:
      self._class_counter = count()
    return f'_class{next(self._class_counter)}'


def add_opt_attrs(attrs:Dict[str,Any], *pairs:Tuple[str, Any], **items:Any) -> None:
  'Add the items in `*pairs` and `**items` attrs, excluding any None values.'
  for k, v in chain(pairs, items.items()):
    if v is None: continue
    assert k not in attrs, k
    attrs[k] = v


def esc_xml_text(val:Any) -> str:
  'HTML-escape the string representation of `val`.'
  # TODO: add options to support whitespace escaping?
  return html_escape(str(val), quote=False)


def esc_xml_attr(val:Any) -> str:
  'HTML-escape the string representation of `val`, including quote characters.'
  return html_escape(str(val), quote=True)

