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

from lxml.etree import _Element as LxmlElement, Comment, fromstring as parse_xml_data, QName, XMLSyntaxError

from ..exceptions import DeleteNode, FlattenNode, OmitNode


DeleteNode = DeleteNode
FlattenNode = FlattenNode

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
    tag = convert_etree_tag_to_str(el.tag, self.comment_tag)
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
    tag = convert_etree_tag_to_str(el.tag, self.comment_tag)
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


def convert_etree_tag_to_str(tag:str|bytes|bytearray|QName|Callable, comment_tag:str) -> str:
  match tag:
    case str(): return tag
    case bytes()|bytearray(): return tag.decode()
    case QName(): return tag.text
    case _:
      if tag == Comment: # Note: `Comment` is a function object, not a type
        if comment_tag:
          return comment_tag
        else:
          raise OmitNode()
      raise TypeError(f'Invalid tag type: {type(tag).__name__}; tag: {tag!r}')


def main() -> None:
  from argparse import ArgumentParser
  from sys import stdin

  from pithy.io import outM

  arg_parser = ArgumentParser(description='Convert XML to an xmldict dictionary and render it to stdout.')
  arg_parser.add_argument('paths', nargs='+', help='XML files to convert. Pass "-" to read from stdin.')
  arg_parser.add_argument('-interleaved', action='store_true', help='Use the interleaved strategy.')
  args = arg_parser.parse_args()
  for path in args.paths:
    if path == '-':
      path = '<stdin>'
      data = stdin.read()
    else:
      with open(path, 'rb') as f:
        data = f.read()
    parser = XmlDictParser(children_key='-', comment_tag='!--')
    parse = parser.parse_interleaved if args.interleaved else parser.parse
    xmldict = parse(data)
    outM(path, xmldict)


if __name__ == '__main__': main()
