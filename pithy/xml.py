# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
XML tools.
'''

from enum import Enum
from html import escape as html_escape
from io import StringIO
from itertools import chain
from types import TracebackType
from typing import Any, ContextManager, Dict, List, Optional, Sequence, TextIO, Tuple, Type, TypeVar, Union


_Self = TypeVar('_Self', bound='XmlWriter')

XmlAttrs = Optional[Dict[str,Any]]


class XmlWriter(ContextManager):
  '''
  XmlWriter is a ContextManager class that outputs XML text to a file (stdout by default).
  It uses the __enter__ and __exit__ methods to automatically output open and close tags.
  XmlWriter can be subclassed to provide convenient Python APIs; see pithy.html and pithy.svg.
  '''

  class Status(Enum):
    INITED = 0
    ENTERED = 1
    EXITED = 2

  replaced_attrs = {
    'class_' : 'class',
  }

  def __init__(self, tag:str, file:TextIO=None, attrs:XmlAttrs=None, **extra_attrs:Any) -> None:
    '''
    `attrs` is provided as a named parameter to avoid excessive copying of attributes into kwargs dicts,
    and to support XML attributes that contain non-identifier characters.
    The `extra_attrs` kwargs is also provided for convenience.
    '''
    self.file = file or StringIO()
    self.tag = tag
    self.attrs = {} if attrs is None else attrs
    self.attrs.update(extra_attrs)
    self.status = XmlWriter.Status.INITED
    self.write(f'<{self.tag}{self.fmt_attrs(self.attrs)}>')


  def __enter__(self:_Self) -> _Self:
    self.status = XmlWriter.Status.ENTERED
    return self


  def __exit__(self, exc_type:Optional[Type[BaseException]], exc_value:Optional[BaseException],
   traceback: Optional[TracebackType]) -> None:
    if exc_type is not None: return None # Propagate exception by returning falsy.
    self.status = XmlWriter.Status.EXITED
    self.write(f'</{self.tag}>')
    return None


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


  @property
  def string(self):
    if not isinstance(self.file, StringIO):
      raise TypeError(f'{self} cannot get string value for non-StringIO backing file: {self.file}')
    return self.file.getvalue()

  def write(self, *items:Any, sep='') -> None:
    print(*items, sep=sep, file=self.file)


  def leaf(self, tag:str, attrs:XmlAttrs) -> None:
    self.write(f'<{tag}{self.fmt_attrs(attrs)}/>')


  def leaf_text(self, tag:str, attrs:XmlAttrs, text:str) -> None:
    'Output a non-nesting XML element that contains text between the open and close tags.'
    self.write(f'<{tag}{self.fmt_attrs(attrs)}>{esc_xml_text(text)}</{tag}>')


  def sub(self, tag:str, attrs:XmlAttrs) -> 'XmlWriter':
    'Create a child XmlWriter for use in a `with` context to represent a nesting XML element.'
    return XmlWriter(file=self.file, tag=tag, attrs=attrs)



def add_opt_attrs(attrs:Dict[str,Any], *pairs:Tuple[str, Any], **items:Any) -> None:
  'Add the items in `*pairs` and `**items` attrs, excluding any None values.'

  for k, v in chain(pairs, items.items()):
    if v is None: continue
    assert k not in attrs, k
    attrs[k] = v


def esc_xml_text(val:Any) -> str:
  'HTML-escape the string representation of `val`.'
  return html_escape(str(val), quote=False)


def esc_xml_attr(val:Any) -> str:
  'HTML-escape the string representation of `val`, including quote characters.'
  return html_escape(str(val), quote=True)

