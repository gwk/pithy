# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from xml.etree.ElementTree import Comment, Element, ParseError, QName, SubElement

from pithy.xml.xmldict import convert_etree_tag_to_str, XmlDictParser, XmlError
from utest import utest, utest_exc, utest_run, utest_val


parser = XmlDictParser(children_key='-')
source = '<root xmlns="urn:test" z="2" a="1"> Hello &amp; world <child> value </child><!-- note --></root>'
expected = {'': '{urn:test}root', 'a': '1', 'z': '2', 'text': 'Hello & world',
  '-': [{'': '{urn:test}child', 'text': 'value'}]}
utest(expected, parser.parse, source)
utest(expected, parser.parse, source.encode())
utest(['', 'a', 'z', 'text', '-'], lambda: list(parser.parse(source)))
utest({'': 'root', 'text': 'caf\u00e9'}, parser.parse,
  b'<?xml version="1.0" encoding="ISO-8859-1"?><root>caf\xe9</root>')
utest('{urn:test}root', convert_etree_tag_to_str, QName('urn:test', 'root'), '')


@utest_run
def _() -> None:
  'Accept standard-library elements, including qualified names and comments.'
  root = Element('{urn:test}root')
  SubElement(root, 'child').text = ' value '
  root.append(Comment(' note '))
  utest({'': '{urn:test}root', '-': [{'': 'child', 'text': 'value'}]}, parser.parse, root)
  with_comments = XmlDictParser(children_key='-', comment_tag='!--')
  utest({'': '{urn:test}root', '-': [{'': 'child', 'text': 'value'}, {'': '!--', 'text': 'note'}]},
    with_comments.parse, root)


for parse_name in ('parse', 'parse_interleaved'):
  for comment_tag in ('', '!--'):
    parse = getattr(XmlDictParser(children_key='-', comment_tag=comment_tag), parse_name)
    children = [{'': '!--', 'text': 'note'}] if comment_tag else []
    utest({'': 'root', **({'-': children} if children else {})}, parse, '<root><!-- note --></root>')
  parse = getattr(parser, parse_name)
  utest_exc(XmlError, parse, '<root>')
  utest_exc(XmlError, parse, '<root>&undefined;</root>')
  utest_exc(TypeError, parse, '<root><?instruction value?></root>')

utest({'': 'root', '-': ['before', {'': 'child', 'text': 'inside'}]}, parser.parse_interleaved,
  '<root> before <child> inside </child></root>')


@utest_run
def _() -> None:
  'Preserve the parser error as the cause of XmlError.'
  try: parser.parse('<root>')
  except XmlError as e:
    utest_val(True, isinstance(e.__cause__, ParseError))
  else: raise AssertionError('Expected XmlError.')
