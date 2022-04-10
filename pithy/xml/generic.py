# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Generic dictionary trees for XML.

Trees are represented as ordinary dictionaries:
* The element tag is stored under the '' key.
* Attributes are sorted and stored under string keys.
* If `text_key` is supplied, then text is stored under that key, and tail text is omitted.
* Otherwise, text is interleaved with child elements.
* Node children are stored together in a list under the children key, which defaults to '-'.
* The children list is omitted if the node has no children.

The hyphen key is chosen as the default children key because it is not a legal XML name; see: https://www.w3.org/TR/xml/#NT-Name.
Similarly, we use '!COMMENT' as the tag for comments.

This representation makes use of stable dictionary ordering.
The tag is always first, followed by sorted attributes, followed by the children list.
'''

import re
from typing import Callable, Collection, Container, Iterator, Optional, cast
from lxml.etree import Comment, _Element as LxmlElement, fromstring as parse_xml_data

from ..exceptions import DeleteNode
from .escape import fmt_attr_items


GenericXmlChild = str|dict
GenericXml = dict[str,GenericXmlChild|list[GenericXmlChild]]


def gxml_from_etree(xml:str|bytes|LxmlElement, *, children_key:str='-', text_key:Optional[str]=None) -> GenericXml:
  '''
  Build a generic XML tree from an XML string, bytes or lxml.etree.Element.
  Note that any text or tail on the root element is discarded.
  '''
  if isinstance(xml, (str,bytes)): xml = parse_xml_data(xml)
  assert isinstance(xml, LxmlElement)
  return _build_gxml_from_etree(xml, children_key=children_key, text_key=text_key)


def _build_gxml_from_etree(el:LxmlElement, children_key:str, text_key:Optional[str]) -> GenericXml:
  'Recursive helper function for gxml_from_etree.'
  tag = el.tag
  if tag == Comment: tag = '!COMMENT'
  res:GenericXml = {'': tag}
  res.update(sorted(el.items())) # type: ignore
  children:list[GenericXmlChild] = []
  if text := el.text:
    if text_key is not None:
      res[text_key] = text
    else:
      children.append(text)
  children.extend(_build_gxml_from_etree(child, children_key, text_key) for child in el)
  if text_key is None and el.tail:
    children.append(el.tail)
  if children:
    res[children_key] = children
  return res


def gxml_iter(xml:GenericXml, children_key:str='-') -> Iterator[GenericXmlChild]:
  try: children = xml[children_key]
  except KeyError: return
  yield from children


def gxml_iter_child_els(xml:GenericXml, children_key:str='-') -> Iterator[GenericXml]:
  try: children = xml[children_key]
  except KeyError: return
  for child in children:
    if isinstance(child, dict): yield child


def gxml_child_collection(xml:GenericXml, children_key:str='-') -> Collection[GenericXmlChild]:
  return xml.get(children_key, ())


def gen_gxml_text(xml:GenericXml, children_key:str='-') -> Iterator[str]:
  if xml[''] == '!COMMENT': return
  try: children = xml[children_key]
  except KeyError: return
  for c in children:
    if isinstance(c, str): yield c
    else: yield from gen_gxml_text(c, children_key=children_key)


def gxml_text(xml:GenericXml, children_key:str='-') -> str:
  return ''.join(gen_gxml_text(xml, children_key=children_key))


def clean_gxml_whitespace(xml:GenericXml, ws_sensitive_tags:Container[str], children_key:str='-') -> None:

  def _clean(xml:GenericXml) -> None:
    if children_key not in xml: return
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

  visit_gxml(xml, pre=_clean, children_key=children_key)


_ws_re = re.compile(r'\s+')


def render_gxml(xml:GenericXml, void_elements:Container[str], children_key:str='-') -> Iterator[str]:
  tag = xml['']
  if tag == '!COMMENT': raise NotImplementedError('Comments are not yet supported')
  children = gxml_child_collection(xml, children_key=children_key)

  if (not children) and void_elements:
    self_closing = (tag in void_elements)
  else:
    self_closing = (not children)

  attrs_str = fmt_attr_items(xml.items(), ignore=('', children_key))
  head = f'<{tag}{attrs_str}'

  if self_closing:
    yield head + '/>'
  else:
    yield head + '>'
    for child in children:
      if isinstance(child, dict):
        yield from render_gxml(child, void_elements=void_elements, children_key=children_key)
      else:
        yield str(child)
    yield f'</{tag}>'


def visit_gxml(xml:GenericXml, children_key:str='-', *, pre:Callable[[GenericXml],None]=None, post:Callable[[GenericXml],None]=None) -> None:
  if pre is not None: pre(xml)
  try: children = cast(list[GenericXml], xml[children_key])
  except KeyError: pass
  else:
    del_indexes = set()
    for i, child in enumerate(children):
      try: visit_gxml(child, children_key=children_key, pre=pre, post=post)
      except DeleteNode: del_indexes.add(i)
    if del_indexes:
      children[:] = [child for i, child in enumerate(children) if i not in del_indexes]
  if post is not None: post(xml)
