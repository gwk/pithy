# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
`craft-xml-dataclasses` is a tool to generate dataclasses from a collection of XML example documents.
'''

import re
from argparse import ArgumentParser, Namespace
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Callable, TextIO

from lxml.etree import Comment, XMLSyntaxError, _Element, fromstring as parse_xml_data
from pithy.io import errD, errL
from pithy.iterable import single_el
from pithy.py import sanitize_for_py_keywords
from yaml import safe_load as load_yaml


def main() -> None:
  arg_parser = ArgumentParser(description='Generate dataclasses from XML example documents.')
  arg_parser.add_argument('-base', default='', help='Base class name. Also used as a prefix for generated subclass names.')
  arg_parser.add_argument('-output', required=True, help='Generated code output file.')
  arg_parser.add_argument('-comment-examples', action='store_true', help='Add comments to each attribute with example values.')
  arg_parser.add_argument('-input-lists', nargs='+', help='Text file containing paths to XML example documents.')
  arg_parser.add_argument('-hint-file', help='Data file containing hints for datatype names.')
  arg_parser.add_argument('paths', nargs='*', help='Input example XML files.')

  args = arg_parser.parse_args()

  if args.hint_file:
    with open(args.hint_file, 'r') as f:
      raw_hints = load_yaml(f)
      # TODO
    hints = Hints()
  else:
    hints = Hints()

  summaries:dict[str,ElementSummary] = {}

  paths = list(args.paths)
  for input_list in args.input_lists:
    with open(input_list, 'r') as f:
      paths.extend(line.strip() for line in f)

  for path in paths:
    parse_path(args, path=path, summaries=summaries)

  for summary in summaries.values():
    summary.process()

  with open(args.output, 'w') as f:
    write_code(args, f, summaries=summaries)


@dataclass
class Hints:
  inheritance:dict[str,str] = field(default_factory=dict)
  tag_single_child_attr_tags:dict[str,set[str]] = field(default_factory=dict)
  tag_plural_child_attr_tags:dict[str,set[str]] = field(default_factory=dict)


@dataclass
class ElementSummary:
  tag:str
  name:str
  count: int = 0
  attrs:defaultdict[str,Counter[str]] = field(default_factory=lambda:defaultdict(Counter)) # Maps attribute name to Counter of attribute values.
  child_tags:set[str] = field(default_factory=set) # All child tags.
  plural_child_tags:set[str] = field(default_factory=set) # Child tags that appear more than once in a single parent.
  single_child_tag_counts:Counter[str] = field(default_factory=Counter) # Child tags that appear at most once in a single parent, counted over all examples.
  child_attr_tags:set[str] = field(default_factory=set) # Child tags that appear at most once in a single parent, treated as attributes.
  text: set[str] = field(default_factory=set)
  tail: set[str] = field(default_factory=set)

  def process(self) -> None:
    child_attr_tags = tags_to_child_attr_tags.get(self.tag, set())

    for tag in child_attr_tags:
      if tag in self.attrs:
        print(f'Warning: {self.tag!r} has proposed single-child tag {tag!r} that is also an attribute; skipping.')
      else:
        if tag in self.plural_child_tags:
          print(f'Warning: {self.tag!r} has proposed single-child tag {tag!r} that appears more than once in a single parent.')
        self.child_attr_tags.add(tag)

    for tag in self.child_attr_tags:
      self.child_tags.remove(tag)
      self.attrs[tag] = Counter() # Empty counter is ignored in attr_line_parts().


def parse_path(args:Namespace, path:str, summaries:dict[str,ElementSummary]) -> None:
  #print(path)
  with open(path, 'rb') as f:
    data = f.read()
  if not data:
    errL(f'{path}: empty file, skipping.')
    return
  if b'<<<<<<<' in data:
    errL(f'{path}: error: found "<<<<<<<" marker, skipping.')
    return
  try: doc = parse_xml_data(data)
  except XMLSyntaxError as e:
    errL(f'{path}: error: {e}')
    return
  parse_element(element=doc, base=args.base, summaries=summaries)


def parse_element(element:_Element, base:str, summaries:dict[str,ElementSummary]) -> None:
  tag = clean_tag(element.tag)

  try: summary = summaries[tag]
  except KeyError:
    summary = ElementSummary(tag=tag, name=class_name_for_tag(base, tag))
    summaries[tag] = summary

  summary.count += 1

  for k, v in element.attrib.items():
    assert isinstance(k, str)
    assert isinstance(v, str)
    attr_counter = summary.attrs[k]
    attr_counter[v] += 1

  child_tag_counts = Counter[str]()
  for child in element:
    child_tag = clean_tag(child.tag)
    child_tag_counts[child_tag] += 1
    parse_element(child, base, summaries)

  summary.child_tags.update(child_tag_counts.keys())
  summary.plural_child_tags.update(child_tag for child_tag, count in child_tag_counts.items() if count > 1)
  summary.single_child_tag_counts.update(child_tag for child_tag, count in child_tag_counts.items() if count == 1)

  if element.text and element.text.strip():
    summary.text.add(element.text)
  if element.tail and element.tail.strip():
    summary.tail.add(element.tail)


def clean_tag(tag:str) -> str:
    if isinstance(tag, str):
      return tag
    elif tag is Comment: # type: ignore # Statement is in fact reachable.
      return 'Comment' # TODO: make this less likely to collide.
    else:
      raise TypeError(f'Unknown element tag type: {tag}')


def write_code(args:Namespace, f:TextIO, summaries:dict[str,ElementSummary]) -> None:
  base = args.base

  def outL(*s:str) -> None:
    f.write(''.join(s))
    f.write('\n')

  outL('# Generated by craft-xml-dataclasses.')
  outL()
  outL('from dataclasses import dataclass, field')
  outL('from typing import Any, ClassVar, Optional, Type, Union')
  outL()
  outL('from pithy.xml.datatypes import XmlDatatype, XmlComment')
  outL()
  outL()
  outL(f'class {base}(XmlDatatype):')
  outL()
  outL('  @classmethod')
  outL('  def _child_type(cls) -> Type[XmlDatatype]:')
  outL('    "Static type of child element type, if all children are of the same type, or else the base type."')
  outL(f'    return {base}')
  outL()
  outL(f'  _datatypes:ClassVar[dict[str,Type[XmlDatatype]]] = {{}}')

  for summary in summaries.values():
    write_class(args=args, outL=outL, summary=summary)

  outL()
  outL()
  outL(f'{base}._datatypes = {{')
  outL('  "!COMMENT": XmlComment,')
  for summary in summaries.values():
    outL(f'  {summary.tag!r}: {summary.name},')
  outL('}')


def write_class(args:Namespace, outL:Callable[...,None], summary:ElementSummary) -> None:
  base = args.base
  add_comments = args.comment_examples
  class_name = class_name_for_tag(base, summary.tag)

  if tags := summary.child_tags:
    if len(tags) == 1:
      child_type = class_name_for_tag(base, single_el(tags))
    else:
      child_type = base
  else:
    child_type = None

  outL()
  outL()
  outL(f'@dataclass')
  outL(f'class {class_name}({base}):', (f'# {summary.count} examples.' if add_comments else ''))
  outL(f'  _tag:ClassVar[str] = {summary.tag!r}')

  if summary.child_attr_tags:
    outL(f'  _child_attr_tags:ClassVar[frozenset[str]] = frozenset({summary.child_attr_tags!r})')

  if child_type and child_type != base:
    outL()
    outL('  @classmethod')
    outL(f'  def _child_type(cls) -> Type[{base!r}]: return {child_type}')

  if summary.attrs:
    outL()
    attr_lines_parts = [attr_line_parts(base, summary, raw_name, vals) for raw_name, vals in summary.attrs.items()]
    attr_lines_parts.sort(key=lambda l: (bool(l[2]), l[0])) # Sort by presence of default first, then name.
    for name, attr_type, dflt, comment in attr_lines_parts:
      dflt_str = f' = {dflt}' if dflt else ''
      comment_str = f' # {comment}' if add_comments else ''
      outL(f'  {name}:{attr_type}{dflt_str}{comment_str}')

  if summary.text:
    outL()
    comment = repr(sorted(summary.text))
    outL(f'  text:str = ""', f' # {comment}' if add_comments else '')

  if child_type:
    outL()
    outL(f'  children:list[{child_type!r}] = field(default_factory=list)')

  if summary.tail:
    outL()
    comment = repr(sorted(summary.tail))
    outL(f'  tail:str = ""', f' # {comment}' if add_comments else '')


def class_name_for_tag(base:str, tag:str) -> str:
  assert isinstance(tag, str), tag
  name = sanitize_for_py_keywords(tag.replace('-', '_'))
  return base + name[0].upper() + name[1:]


def attr_line_parts(base:str, summary:ElementSummary, raw_name:str, vals:Counter[str]) -> tuple[str,str,str,str]:

  if raw_name in summary.child_attr_tags: # This attribute is for a single-occurence child.
    plain_type = repr(class_name_for_tag(base, raw_name))
    count = summary.single_child_tag_counts[raw_name]
  else:
    count = sum(vals.values())
    plain_type = guess_attr_type(summary.count, vals)

  name = sanitize_for_py_keywords(raw_name.replace('-', '_'))
  attr_type = plain_type
  dflt = ''
  if count < summary.count: # Optional.
    attr_type = f'Optional[{plain_type}]'
    dflt = 'None'
    if plain_type == 'bool': # Try to use a plain bool with default of the missing value.
      bool_vals = set(bool_strings[v.lower()] for v in vals)
      if len(bool_vals) == 1:
        dflt = repr(not bool_vals.pop())
        attr_type = plain_type

  comment = repr(sorted(vals))
  return (name, attr_type, dflt, comment)


def guess_attr_type(count:int, vals:Counter[str]) -> str:
  if all(int_re.fullmatch(v) for v in vals): return 'int'
  elif all(float_re.fullmatch(v) for v in vals): return 'float'
  elif all((v.lower() in bool_strings) for v in vals): return 'bool'
  return 'str'


int_re = re.compile(r'[+-]?[0-9]+')
float_re = re.compile(r'[+-]?[0-9]+\.?[0-9]*')

bool_strings = {
  'true': True,
  'false': False,
  'yes': True,
  'no': False,
}


tags_to_child_attr_tags:dict[str,set[str]] = {
  'button': { 'connections', 'constraints', 'userDefinedRuntimeAttributes' },
  'label':  { 'constraints', 'userDefinedRuntimeAttributes' },
}

if __name__ == '__main__': main()
