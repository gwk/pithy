# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
XML tools.
'''

from itertools import chain
from sys import stdout
from html import escape as html_escape
from types import TracebackType
from typing import Any, ContextManager, Dict, List, Optional, Sequence, TextIO, Tuple, Type, Union

FileOrPath = Union[TextIO, str]


class XmlSubtree(ContextManager):
  '''
  An XmlSubbtree represents a non-leaf node of the XML tree.
  '''


  def __init__(self, writer:'XmlWriter', tag:str, attrs:Dict[str,Any]=None, children:Sequence[str]=()) -> None:
    self.writer = writer
    self.tag = tag
    self.attrs = {} if attrs is None else attrs
    self.children = children


  def __enter__(self) -> 'XmlSubtree':
    self.writer.write(f'<{self.tag}{fmt_xml_attrs(self.attrs)}>')
    self.writer._stack.append((id(self), self.tag)) # use id to avoid ref cycle.
    self.attrs = None # type: ignore # poison.
    for child in self.children:
      self.writer.write(child)
    self.children = None # type: ignore # poison.
    return self


  def __exit__(self, exc_type:Optional[Type[BaseException]], exc_value:Optional[BaseException],
  traceback: Optional[TracebackType]) -> None:
    exp = self.writer._stack.pop()
    act = (id(self), self.tag)
    if act != exp:
      raise Exception(f'XmlWriter top-of-stack {exp} does not match context: {act}')
    self.writer.write(f'</{self.tag}>')



class XmlWriter(ContextManager):
  '''
  XmlWriter is a ContextManager class that outputs XML text to a file (stdout by default).
  It maintains a stack of XmlSubtree objects to guarantee that XML tags get closed appropriately.
  '''


  def __init__(self, tag:str, file_or_path:FileOrPath=stdout, *attr_pairs:Tuple[str, str], **attrs:Any) -> None:
    if isinstance(file_or_path, str):
      self.file = open(file_or_path, 'w')
    else:
      self.file = file_or_path
    self.tag = tag
    self.attrs = dict(attr_pairs)
    self.attrs.update(attrs)
    self._stack: List[Tuple[int, str]] = []


  def __del__(self) -> None:
    if self._stack:
      raise Exception(f'XmlWriter finalized before tag stack was popped; did you forget to use a `with` context?')


  def __enter__(self) -> 'XmlWriter':
    self.write(f'<{self.tag}{fmt_xml_attrs(self.attrs)}>')
    return self


  def __exit__(self, exc_type, exc_val, exc_tb) -> None:
    if exc_type is not None: return # propagate exception.
    self.write('</svg>')
    if self._stack:
      raise Exception(f'XmlWriter context exiting with non-empty stack: {self._stack}')
    return None


  @property
  def indent(self) -> int:
    return len(self._stack)


  def write(self, *items:Any) -> None:
    print('  ' * self.indent, *items, sep='', file=self.file)


  def leaf(self, tag:str, attrs:Dict[str,Any]) -> None:
    self.write(f'<{tag}{fmt_xml_attrs(attrs)}/>')


  def leaf_text(self, tag:str, attrs:Dict[str,Any], text:str) -> None:
    'Output a non-nesting XML element that contains text between the open and close tags.'
    self.write(f'<{tag}{fmt_xml_attrs(attrs)}>{esc_text(text)}</{tag}>')


  def subtree(self, tag:str, attrs:Dict[str,Any], children:Sequence[str]=()) -> 'XmlSubtree':
    'Create an XmlSubtree for use in a `with` context to represent a nesting XML element.'
    return XmlSubtree(writer=self, tag=tag, attrs=attrs, children=children)



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
