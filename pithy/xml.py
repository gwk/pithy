# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
XML tools.
'''

from enum import Enum
from itertools import chain
from sys import stdout
from html import escape as html_escape
from types import TracebackType
from typing import Any, ContextManager, Dict, List, Optional, Sequence, TextIO, Tuple, Type, Union


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

  def __init__(self, tag:str, file:TextIO=stdout, attrs:Dict[str,Any]=None, children:Sequence[str]=(),
   *attr_pairs:Tuple[str, str], **extra_attrs:Any) -> None:
    '''
    `attrs` is provided as a named parameter to avoid excessive copying of attributes into kwargs dicts.
    However, `extra_attrs` kwargs is also supported for convenience;
    `attr_pairs` is provided to allow for XML attribute names that cannot be mapped from python identifiers, e.g. 'xlink:href'.
    `children` allows the initializer to create child elements that will are buffered until context entry.
    '''
    self.file = file
    self.tag = tag
    self.attrs = {} if attrs is None else attrs
    self.attrs.update(attr_pairs)
    self.attrs.update(extra_attrs)
    self.children = children
    self.status = XmlWriter.Status.INITED


  def __enter__(self) -> 'XmlWriter':
    self.write(f'<{self.tag}{fmt_xml_attrs(self.attrs)}>')
    # Print before updating status to get proper indentation.
    self.status = XmlWriter.Status.ENTERED
    for child in self.children:
      self.write(child)
    return self


  def __exit__(self, exc_type:Optional[Type[BaseException]], exc_value:Optional[BaseException],
   traceback: Optional[TracebackType]) -> None:
    if exc_type is not None: return None # Propagate exception by returning falsy.
    self.status = XmlWriter.Status.EXITED
    self.write(f'</{self.tag}>')
    return None


  def write(self, *items:Any) -> None:
    print(*items, sep='', file=self.file)


  def leaf(self, tag:str, attrs:Dict[str,Any]) -> None:
    self.write(f'<{tag}{fmt_xml_attrs(attrs)}/>')


  def leaf_text(self, tag:str, attrs:Dict[str,Any], text:str) -> None:
    'Output a non-nesting XML element that contains text between the open and close tags.'
    self.write(f'<{tag}{fmt_xml_attrs(attrs)}>{esc_text(text)}</{tag}>')


  def sub(self, tag:str, attrs:Dict[str,Any], children:Sequence[str]=()) -> 'XmlWriter':
    'Create a child XmlWriter for use in a `with` context to represent a nesting XML element.'
    return XmlWriter(file=self.file, tag=tag, attrs=attrs, children=children)



def add_opt_attrs(attrs:Dict[str, Any], *pairs:Tuple[str, Any], **items:Any) -> None:
  'Add the items in `*pairs` and `**items` attrs, excluding any None values.'
  for k, v in chain(pairs, items.items()):
    if v is None: continue
    assert k not in attrs, k
    attrs[k] = v


def fmt_xml_attrs(attrs:Optional[Dict[str, Any]]) -> str:
  'Format the `attrs` dict into XML key-value attributes.'
  if not attrs: return ''
  parts: List[str] = []
  for k, v in attrs.items():
    if v is None:
      v = 'none'
    else:
      k = _replaced_attrs.get(k, k)
    parts.append(f' {esc_attr(k.replace("_", "-"))}="{esc_attr(v)}"')
  return ''.join(parts)


def esc_text(val:Any) -> str:
  'HTML-escape the string representation of `val`.'
  return html_escape(str(val), quote=False)


def esc_attr(val:Any) -> str:
  'HTML-escape the string representation of `val`, including quote characters.'
  return html_escape(str(val), quote=True)


_replaced_attrs = {
  'class_' : 'class',
  'href': 'xlink:href', # safari Version 11.1.1 requires this, even though xlink is deprecated in svg 2 standard.
}
