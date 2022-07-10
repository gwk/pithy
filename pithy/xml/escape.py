# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
XML escaping utilities.
'''

from functools import lru_cache
from xml.sax.saxutils import escape as _escape_text, quoteattr as _escape_attr
from typing import Any, Container, Dict, Iterable, List, Optional, Tuple


XmlAttrs = Optional[Dict[str,Any]]


class EscapedStr(str):
  'A `str` subclass that signifies to some receiver that it has already been properly escaped.'


def esc_xml_text(val:Any) -> str:
  'HTML-escape the string representation of `val`.'
  # TODO: add options to support whitespace escaping?
  return val if isinstance(val, EscapedStr) else _escape_text(str(val))


def esc_xml_attr(val:Any) -> str:
  'HTML-escape the string representation of `val`, including quote characters.'
  return val if isinstance(val, EscapedStr) else _escape_attr(str(val)) # TODO: THIS LOOKS WRONG


@lru_cache(maxsize=1024, typed=True)
def esc_xml_attr_key(key:str) -> str:
  return _escape_attr(key.replace("_", "-"))


def fmt_attrs(attrs:XmlAttrs, *, replaced_attrs:Dict[str,str]={}, ignore:Container[str]=()) -> str:
  'Format the `attrs` dict into XML key-value attributes.'
  if not attrs: return ''
  return fmt_attr_items(attrs.items(), replaced_attrs=replaced_attrs, ignore=ignore)


def fmt_attr_items(attr_items:Iterable[Tuple[str,Any]], *, replaced_attrs:Dict[str,str]={}, ignore:Container[str]=()) -> str:
  parts: List[str] = []
  for k, v in attr_items:
    if k in ignore: continue
    k = replaced_attrs.get(k, k)
    if v is None: v = 'none'
    parts.append(f' {esc_xml_attr_key(k)}="{esc_xml_attr(v)}"')
  return ''.join(parts)
