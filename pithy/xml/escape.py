# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
XML escaping utilities.
'''

from functools import lru_cache
from typing import Any, Container, Iterable
from xml.sax.saxutils import escape as _escape_text, quoteattr as _escape_attr

from ..string import EscapedStr


XmlAttrs = dict[str,Any]|None



def esc_xml_text(val:Any) -> str:
  'HTML-escape the string representation of `val`.'
  # TODO: add options to support whitespace escaping?
  return val.string if isinstance(val, EscapedStr) else _escape_text(str(val))


def esc_xml_attr(val:Any) -> str:
  'HTML-escape the string representation of `val`, including quote characters.'
  return val.string if isinstance(val, EscapedStr) else _escape_attr(str(val))


@lru_cache(maxsize=1024, typed=True)
def esc_xml_attr_key(key:str) -> str:
  return _escape_attr(key.replace("_", "-"))


def fmt_attrs(attrs:XmlAttrs, *, replaced_attrs:dict[str,str]={}, ignore:Container[str]=()) -> str:
  'Format the `attrs` dict into XML key-value attributes.'
  if not attrs: return ''
  return fmt_attr_items(attrs.items(), replaced_attrs=replaced_attrs, ignore=ignore)


def fmt_attr_items(attr_items:Iterable[tuple[str,Any]], *, replaced_attrs:dict[str,str]={}, ignore:Container[str]=()) -> str:
  parts: list[str] = []
  for k, v in attr_items:
    if k in ignore: continue
    k = replaced_attrs.get(k, k)
    if v is None: v = 'none'
    parts.append(f' {esc_xml_attr_key(k)}="{esc_xml_attr(v)}"')
  return ''.join(parts)
