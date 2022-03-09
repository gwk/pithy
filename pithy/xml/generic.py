# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Generic dictionary trees for XML.

Trees are represented as ordinary dictionaries:
* The element tag is stored under the '' key.
* Attributes are sosrted and stored under string keys.
* Node children and text are stored together in a list under the '-' key.
* The children item is omitted if the node has no children.

The hyphen key is chosen for children because it is not a legal XML name; see: https://www.w3.org/TR/xml/#NT-Name.
Similarly, we use '!COMMENT' as the tag for comments.

This representation makes use of stable dictionary ordering.
The tag is always first, followed by sorted attributes, followed by the children list.
'''

import re
from typing import Callable, Collection, Container, Iterator, cast
from xml.etree.ElementTree import Element, fromstring as parse_xml_data

from lxml.etree import Comment

from ..exceptions import DeleteNode
from .escape import fmt_attr_items


GenericXmlChild = str|dict
GenericXml = dict[str,GenericXmlChild|list[GenericXmlChild]]


def gxml_from_etree(xml:str|bytes|Element) -> GenericXml:
  '''
  Build a generic XML tree from an XML string, bytes or lxml.etree.Element.
  Note that any text or tail on the root element is discarded.
  '''
  if isinstance(xml, (str,bytes)): xml = parse_xml_data(xml)
  assert isinstance(xml, Element)
  return _build_gxml_from_etree(xml)


def _build_gxml_from_etree(el:Element) -> GenericXml:
  'Recursive helper function for gxml_from_etree.'
  tag = el.tag
  if tag == Comment: tag = '!COMMENT'
  res:GenericXml = {'': tag}
  res.update(sorted(el.items()))
  children:list[GenericXmlChild] = []
  if text := el.text:
    children.append(text)
  children.extend(_build_gxml_from_etree(child) for child in el)
  if tail := el.tail:
    children.append(tail)
  if children:
    res['-'] = children
  return res


def gxml_iter(xml:GenericXml) -> Iterator[GenericXmlChild]:
  try: children = xml['-']
  except KeyError: return
  yield from children


def gxml_iter_child_els(xml:GenericXml) -> Iterator[GenericXml]:
  try: children = xml['-']
  except KeyError: return
  for child in children:
    if isinstance(child, dict): yield child


def gxml_child_collection(xml:GenericXml) -> Collection[GenericXmlChild]:
  return xml.get('-', ())


def gen_gxml_text(xml:GenericXml) -> Iterator[str]:
  if xml[''] == '!COMMENT': return
  try: children = xml['-']
  except KeyError: return
  for c in children:
    if isinstance(c, str): yield c
    else: yield from gen_gxml_text(c)


def gxml_text(xml:GenericXml) -> str:
  return ''.join(gen_gxml_text(xml))


def clean_gxml_whitespace(xml:GenericXml, ws_sensitive_tags:Container[str]) -> None:

  def _clean(xml:GenericXml) -> None:
    if '-' not in xml: return
    children:list[GenericXmlChild] = []
    # Consolidate consecutive strings.
    for child in gxml_iter(xml):
      if isinstance(child, str): # Text.
        if not child: continue # Omit empty strings.
        if children and isinstance(children[-1], str): # Consolidate.
          children[-1] += child
        else:
          children.append(child)
      else: # Child element.
        children.append(child)

    tag = xml['']
    if tag not in ws_sensitive_tags: # Clean whitespace.
      for i, child in enumerate(children):
        if not isinstance(child, str): continue
        replacement = '\n' if '\n' in child else ' '
        children[i] = _ws_re.sub(replacement, child)

    xml['-'] = children

  visit_gxml(xml, pre=_clean)


_ws_re = re.compile(r'\s+')


def render_gxml(xml:GenericXml, void_elements:Container[str]) -> Iterator[str]:
  tag = xml['']
  if tag == '!COMMENT': raise NotImplementedError('Comments are not yet supported')
  children = gxml_child_collection(xml)

  if (not children) and void_elements:
    self_closing = (tag in void_elements)
  else:
    self_closing = (not children)

  attrs_str = fmt_attr_items(xml.items(), ignore=gxml_non_attr_keys)
  head = f'<{tag}{attrs_str}'

  if self_closing:
    yield head + '/>'
  else:
    yield head + '>'
    for child in children:
      if isinstance(child, dict):
        yield from render_gxml(child, void_elements=void_elements)
      else:
        yield str(child)
    yield f'</{tag}>'


def visit_gxml(xml:GenericXml, *, pre:Callable[[GenericXml],None]=None, post:Callable[[GenericXml],None]=None) -> None:
  if pre is not None: pre(xml)
  try: children = cast(list[GenericXml], xml['-'])
  except KeyError: pass
  else:
    del_indexes = set()
    for i, child in enumerate(children):
      try: visit_gxml(child, pre=pre, post=post)
      except DeleteNode: del_indexes.add(i)
    if del_indexes:
      children[:] = [child for i, child in enumerate(children) if i not in del_indexes]
  if post is not None: post(xml)


gxml_non_attr_keys = ('', '-')
