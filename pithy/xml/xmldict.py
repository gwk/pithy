# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Convert XML into dictionary trees.

Xml documents are represented as ordinary dictionaries:
* The element tag is stored under the '' key.
* Attributes are sorted and stored under string keys.
* Node children are stored in a list under the children key, which is caller-supplied.

Text is handled in one of two ways; these strategies are implemented as separate functions,
because they the type signature of the result is different for each.

The "simple" version uses `text_key` to store text; tail text is omitted.
This is useful for XML formats designed to represent object trees.

The "interleaved" version stores text (and tail text) interleaved with child nodes.
This is useful for representing "marked up" documents.

In either case the text is omitted if it is empty,
and the children list is omitted if the node has no children.

'-' is a good choice for the children_key because it is not a legal XML name; see: https://www.w3.org/TR/xml/#NT-Name.
All XML comments are discarded.

'_' is another option, because it is unlikely to be used as an XML attribute name but is a legal python attribute,
so it can be used to transtruct directly to python datatypes.

This representation benefits from Python's stable dictionary ordering:
The tag is always first, followed by sorted attributes, followed by the children list.
'''

from dataclasses import dataclass
from typing import Any, Callable

from lxml.etree import _Element as LxmlElement, Comment, fromstring as parse_xml_data, XMLSyntaxError

from ..exceptions import DeleteNode, FlattenNode, OmitNode


XmlDict = dict[str,str|list[dict[str,Any]]] # The "Any" compensates for lack of recursive types in mypy.

XmlDictChild = str|dict[str,Any] # The interleaved strategy has more a complex child type.
XmlInterleavedDict = dict[str,str|list[XmlDictChild]]



class XmlError(Exception): pass


@dataclass
class XmlDictParser:
  children_key:str
  text_key:str = 'text' # Unused for the interleaved strategy.
  text_preprocess:Callable[[str],str] = str.strip
  comment_tag:str = ''


  def parse(self, xml:str|bytes|LxmlElement) -> XmlDict:
    '''
    Build a generic XML tree from an XML string, bytes or lxml.etree.Element.
    Note that any text or tail on the root element is discarded.
    '''
    if isinstance(xml, (str,bytes)):
      try: xml = parse_xml_data(xml)
      except XMLSyntaxError as e:
        raise XmlError(str(e)) from e
    assert isinstance(xml, LxmlElement)
    return self._build_from_etree(xml)


  def parse_interleaved(self, xml:str|bytes|LxmlElement) -> XmlInterleavedDict:
    '''
    Build a generic XML tree from an XML string, bytes or lxml.etree.Element.
    Text and tail values are interleaved with child elements.
    '''
    if isinstance(xml, (str,bytes)):
      try: xml = parse_xml_data(xml)
      except XMLSyntaxError as e:
        raise XmlError(str(e)) from e
    assert isinstance(xml, LxmlElement)
    return self._build_interleaved_from_etree(xml)



  def _build_from_etree(self, el:LxmlElement) -> XmlDict:
    'Recursive helper method for parse.'
    tag = el.tag
    if tag == Comment:
      if self.comment_tag:
        tag = self.comment_tag
      else:
        raise OmitNode()
    res:XmlDict = {'': tag}
    res.update(sorted(el.items()))
    children:list[dict[str,Any]] = []
    if text := el.text:
      if text := self.text_preprocess(text):
        res[self.text_key] = text
    for child_el in el:
      try: child_result = self._build_from_etree(child_el)
      except OmitNode: continue
      children.append(child_result)
    if children:
      res[self.children_key] = children
    return res


  def _build_interleaved_from_etree(self, el:LxmlElement) -> XmlInterleavedDict:
    'Recursive helper method for parse_interleaved.'
    tag = el.tag
    if tag == Comment:
      if self.comment_tag:
        tag = self.comment_tag
      else:
        raise OmitNode()
    res:XmlInterleavedDict = {'': tag}
    res.update(sorted(el.items()))
    children:list[XmlDictChild] = []
    if text := el.text:
      if text := self.text_preprocess(text):
        children.append(text)
    for child_el in el:
      try: child_result = self._build_from_etree(child_el)
      except OmitNode: continue
      children.append(child_result)
    if el.tail:
      if tail := self.text_preprocess(el.tail):
        children.append(tail)
    if children:
      res[self.children_key] = children
    return res
