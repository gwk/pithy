# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Generic dictionary trees for XML.

Trees are represented as ordinary dictionaries:
* The element tag is stored under the '' key;
* attributes are stored under string keys;
* node children and text are stored together under zero-indexed numeric keys.

Note that this scheme relies on the stable ordering of dict items, so it requires Python3.6+.
'''

import re
from typing import Any, Callable, Container, Dict, Iterator, List, Tuple, Union, cast
from xml.etree.ElementTree import Element

from lxml.etree import Comment # type: ignore

from ..exceptions import DeleteNode
from .escape import fmt_attr_items


GenericXmlKey = Union[int,str]
GenericXmlVal = Union[str,Dict]
GenericXml = Dict[GenericXmlKey,GenericXmlVal]


def generic_xml_from_etree(el:Element) -> GenericXml:
  tag = el.tag
  if tag == Comment: tag = '!COMMENT'
  res:Dict = {'': tag}
  res.update(sorted(el.items()))
  idx = 0
  t = el.text
  if t:
    res[idx] = t
    idx += 1
  for child in el:
    res[idx] = generic_xml_from_etree(child)
    idx += 1
    t = child.tail
    if t:
      res[idx] = t
      idx += 1
  return res


def get_tag_attrs_children(xml:GenericXml) -> Tuple[str, List[Tuple[str,Any]], List[Any]]:
  tag = cast(str, xml[''])
  attrs:List[Tuple[str,Any]] = []
  children:List[Tuple[int,Any]] = []
  for p in xml.items():
    k = p[0]
    if isinstance(k, str):
      if k: attrs.append(p) # type: ignore
    else:
      children.append(p) # type: ignore
  return tag, attrs, children


def get_text(xml:GenericXml) -> str:
  text:List[str] = []
  for k, v in xml.items():
    if isinstance(k, int):
      if isinstance(v, dict): text.append(get_text(v))
      else: text.append(str(v))
  return ''.join(text)


def clean_generic_xml_whitespace(xml:GenericXml, ws_sensitive_tags:Container[str]) -> None:

  def _clean(xml:GenericXml) -> None:
    tag = xml['']
    children:List[GenericXmlVal] = []

    # Get all children, consolidating consecutive strings, and simultaneously remove all children from the node.
    for k, v in tuple(xml.items()):
      if isinstance(k, str): continue # Leave tag and attrs untouched.
      del xml[k]
      if isinstance(v, str): # Text.
        if not v: continue # Omit empty strings.
        if children and isinstance(children[-1], str): # Consolidate.
          children[-1] += v
        else:
          children.append(v)
      else: # Child element.
        children.append(v)

    if tag not in ws_sensitive_tags: # Clean whitespace.
      for i in range(len(children)):
        v = children[i]
        if not isinstance(v, str): continue
        replacement = '\n' if '\n' in v else ' '
        children[i] = ws_re.sub(replacement, v)

    xml.update(enumerate(children)) # Replace children with fresh, compacted indices.

  visit_generic_xml(xml, _clean)

ws_re = re.compile(r'\s+')


def render_generic_xml(xml:GenericXml, void_elements:Container[str]) -> Iterator[str]:
  tag, attrs, children = get_tag_attrs_children(xml)

  if (not children) and void_elements:
    self_closing = (tag in void_elements)
  else:
    self_closing = (not children)

  attrs_str = fmt_attr_items(attrs, {})
  head = f'<{tag}{attrs_str}'

  if self_closing:
    yield head + '/>'
  else:
    yield head + '>'
    for _, child in children:
      if isinstance(child, dict):
        yield from render_generic_xml(child, void_elements=void_elements)
      else:
        yield str(child)
    yield f'</{tag}>'


def visit_generic_xml(xml:GenericXml, visit:Callable[[GenericXml],None]) -> None:
  visit(xml)
  for k, v in tuple(xml.items()):
    if isinstance(k, int) and isinstance(v, dict): # Child element.
      try: visit_generic_xml(v, visit)
      except DeleteNode: del xml[k]

