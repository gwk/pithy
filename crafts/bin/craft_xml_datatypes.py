# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
`craft-xml-datatypes` is a tool to generate dataclasses from a collection of XML example documents.
'''

from __future__ import annotations

import re
from argparse import ArgumentParser, Namespace
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Iterator, TextIO

from pithy.dict import dict_remap_keys_mut
from pithy.io import errL
from pithy.iterable import single_el
from pithy.py import sanitize_for_py_keywords_and_type_names
from pithy.string import truncate_repr_with_ellipsis
from pithy.transtruct import bool_vals, Ctx, Transtructor
from pithy.xml.datatypes import ChildAttrInfo
from pithy.xml.xmldict import XmlDict, XmlDictParser, XmlError
from tomli import load as load_toml


def main() -> None:
  arg_parser = ArgumentParser(description='Generate dataclasses from XML example documents.')
  arg_parser.add_argument('-base', default='', help='Base class name. Also used as a prefix for generated subclass names.')
  arg_parser.add_argument('-output', required=True, help='Generated code output file.')
  arg_parser.add_argument('-comment-examples', type=int, help='Add comments to each property with example values.')
  arg_parser.add_argument('-input-lists', nargs='+', help='Text file containing paths to XML example documents.')
  arg_parser.add_argument('-hints', help='Data file containing hints for datatype names.')
  arg_parser.add_argument('-assume-branches', action='store_true', default='',
    help='Specifies that by default nodes by default have children; otherwise by default convert node children to attributes.')
  arg_parser.add_argument('paths', nargs='*', help='Input example XML files.')

  args = arg_parser.parse_args()

  if args.hints:
    with open(args.hints, 'rb') as f:
      raw_hints = load_toml(f)
    hints:Hints = hintTranstructor.transtruct(Hints, raw_hints)
  else:
    hints = {}
  #errD('hints', hints)


  tag_summaries:dict[str,ElementSummary] = { tag: ElementSummary(tag=tag, hint=hint) for tag, hint in hints.items() }
  #^ Prepopulate summaries with hints, so that hinted tags are always included even if they are not present in the corpus.
  #^ Other summary objects have empty hints.

  paths = list(args.paths)
  for input_list in args.input_lists:
    with open(input_list, 'r') as f:
      paths.extend(line.strip() for line in f)

  for path in paths:
    parse_path(path=path, summaries=tag_summaries)

  for summary in tag_summaries.values():
    summary.add_properties(args=args, tag_summaries=tag_summaries)

  summaries = sorted(tag_summaries.values(), key=lambda s: s.sort_key)
  #^ Reorder the summaries for correctness of inheritance processing and output stability.

  for summary in summaries:
    summary.accumulate_attrs_in_superclasses(args=args) # Requires that superclasses come before subclasses.

  for summary in summaries:
    summary.process_final(args=args)

  # TODO: check for unused hints.

  with open(args.output + '.dump', 'w') as f:
    write_dump(args=args, file=f, summaries=summaries)

  with open(args.output, 'w') as f:
    write_code(args=args, file=f, summaries=summaries)


@dataclass
class Hint:
  parent:str = ''
  is_list:bool = False # Whether the tag is flattened into a list; implies that it has no attributes.
  is_branch:bool|None= None # Whether the tag is allowed to have children; None defers to the global argument passed to "-assume-branches".
  #all_children_as_attrs:bool = False # TODO: not yet implemented.
  child_attrs:dict[str,ChildAttrInfo] = field(default_factory=dict) # Child tag names that are treated as attributes.


Hints = dict[str,Hint]


hintTranstructor = Transtructor()

@hintTranstructor.prefigure(ChildAttrInfo)
def prefigure_ChildAttrInfo(class_:type, val:dict, ctx:Ctx) -> dict:
  return dict_remap_keys_mut(val, remap_ChildAttrInfo_keys)


remap_ChildAttrInfo_keys = { 'plural' : 'is_plural' }


@dataclass
class ElementSummary:
  tag:str # Original tag name.
  name:str = '' # Resulting type name.
  parents:list[ElementSummary] = field(default_factory=list) # Gets replaced.
  hint:Hint = field(default_factory=Hint)

  # Collected data.
  count: int = 0 # Total occurrences.
  attrs:defaultdict[str,Counter[str]] = field(default_factory=lambda:defaultdict(Counter)) # Maps attribute name to Counter of attribute values.
  #^ The count of each attribute is compared to the element count, to determine if a given attribute is optional.
  all_child_tags:set[str] = field(default_factory=set) # All child tags.
  single_child_tag_counts:Counter[str] = field(default_factory=Counter) # Child tags that appear at most once in a single parent, counted over all examples.
  plural_child_tags:set[str] = field(default_factory=set) # Child tags that appear more than once in a single parent.

  # Final processed results.
  child_tags:set[str] = field(default_factory=set) # All tags that are treated as children.


  @property
  def sort_key(self) -> tuple[tuple[str,...], str]:
    return (tuple(p.name for p in self.parents), self.name)


  def add_properties(self, args:Namespace,tag_summaries:dict[str,ElementSummary]) -> None:
    'Add properties to this summary after data accumulation.'
    self.name = class_name_for_tag(args.base, self.tag)
    if self.hint.is_branch is None:
      self.hint.is_branch = args.assume_branches
    parents = list(self._parents_reversed(tag_summaries=tag_summaries))
    parents.reverse()
    self.parents = parents

    # TODO: populate attr counter with empty counts for all attrs listed in hints.

    if not self.hint.is_branch:
      # Convert all child tags to attributes unless the tag is explicitly marked with `is_branch`.
      for tag in self.all_child_tags:
        if tag not in self.hint.child_attrs:
          self.hint.child_attrs[tag] = ChildAttrInfo(attr=sanitize_attr(tag))

    for tag, info in self.hint.child_attrs.items():
      if not info.attr: # Fill in the attr name.
        info.attr = sanitize_attr(tag)
      # If the child tag is marked as a list, then propagate that to the ChildAttrInfo in the parent.
      child_summary = tag_summaries.get(tag)
      if child_summary and child_summary.hint.is_list:
        info.is_flattened = True


  def accumulate_attrs_in_superclasses(self, args:Namespace) -> None:
    '''
    Move collected info to parent summaries as appropriate.
    This requires that superclasses are processed before subclasses.
    '''

    for parent in self.parents:
      #print("  parent:" , parent.tag)
      # Transfer attributes to the parent.
      parent.count += self.count
      for attr in parent.attrs:
        try: counter = self.attrs.pop(attr)
        except KeyError: pass
        else:
          #print("      attr:", attr)
          parent.attrs[attr].update(counter)

      for tag in parent.hint.child_attrs:

        try: self.all_child_tags.remove(tag)
        except KeyError: pass
        else: parent.all_child_tags.add(tag)

        try: count = self.single_child_tag_counts.pop(tag)
        except KeyError: pass
        else: parent.single_child_tag_counts[tag] += count

        try: self.plural_child_tags.remove(tag)
        except KeyError: pass
        else: parent.plural_child_tags.add(tag)

      parent.all_child_tags.update(self.all_child_tags)


  def process_final(self, args:Namespace) -> None:
    'Process the collected data.'

    for tag in self.plural_child_tags:
      # Clean up any child tags that were deemed single during collection but turned out to be plural due to examples in subclasses.
      del self.single_child_tag_counts[tag]

    if self.hint.is_list:
      if self.attrs:
        print(f'Warning: {self.tag!r} is marked as list but has attributes: {self.attrs!r}.')
      return

    for tag, info in self.hint.child_attrs.items():
      attr = info.attr
      assert attr
      desc = repr(attr) if (tag == attr) else f'{tag!r}->{attr!r}'
      if attr in self.attrs:
        print(f'error: {self.tag!r} has child attr {desc} that is also an attribute; skipping.')
        continue
      if not info.is_plural and tag in self.plural_child_tags:
        print(f'Warning: {self.tag!r} has single-child attr {desc} that appears more than once in a single parent.')
      self.all_child_tags.discard(tag)
      self.attrs[tag] = Counter() # Empty counter is ignored in attr_line_parts().

    if self.hint.is_branch:
      if not self.attrs:
        print(f'Warning: {self.tag!r} is marked as branch but has no attributes.')
    else:
      if self.all_child_tags:
        print(f'Warning: {self.tag!r} is not marked as a branch but has child tags: {self.all_child_tags!r}.')


  def _parents_reversed(self, tag_summaries:dict[str,ElementSummary]) -> Iterator[ElementSummary]:
    'Yield parents from this element up to but not including the base class.'
    s = self
    while s.hint.parent:
      p = tag_summaries[s.hint.parent]
      yield p
      s = p


def parse_path(path:str, summaries:dict[str,ElementSummary]) -> None:
  with open(path, 'rb') as f:
    data = f.read()
  if not data:
    errL(f'{path}: empty file, skipping.')
    return
  if b'<<<<<<<' in data:
    errL(f'{path}: error: found "<<<<<<<" marker, skipping.')
    return
  try: doc = xmldict_parser.parse(data)
  except XmlError as e:
    errL(f'{path}: error: {e}')
    return
  parse_element(element=doc, summaries=summaries)


xmldict_parser = XmlDictParser(children_key='_', text_key='text')


def parse_element(element:XmlDict, summaries:dict[str,ElementSummary]) -> str:
  tag = element['']
  assert isinstance(tag, str)

  try: summary = summaries[tag]
  except KeyError:
    summary = ElementSummary(tag=tag)
    summaries[tag] = summary

  summary.count += 1

  for k, v in element.items():
    if k == '' or k == '_': continue
    assert isinstance(v, str)
    attr_counter = summary.attrs[k]
    attr_counter[v] += 1

  if children := element.get('_'):
    assert isinstance(children, list)
    child_tag_counts = Counter[str]()
    for child in children:
      child_tag = parse_element(child, summaries)
      child_tag_counts[child_tag] += 1

    summary.all_child_tags.update(child_tag_counts.keys())
    summary.plural_child_tags.update(child_tag for child_tag, count in child_tag_counts.items() if count > 1)
    summary.single_child_tag_counts.update(child_tag for child_tag, count in child_tag_counts.items() if count == 1)

  return tag


def write_dump(args:Namespace, file:TextIO, summaries:Iterable[ElementSummary]) -> None:

  def outL(*objs:Any) -> None:
    file.write(''.join(str(o) for o in objs))
    file.write('\n')

  for summary in summaries:
    parents = ', '.join(s.name for s in summary.parents)
    outL(f'\n\n{summary.name}({parents}): {summary.count}')
    outL(f'has key: {"key" in summary.attrs}')
    outL('\n  attrs:', sorted(f'{k}:{len(c)}' for k, c in summary.attrs.items()))
    outL('\n  child_attrs:', sorted(summary.hint.child_attrs))
    outL('\n  single_child_tags:', sorted(summary.single_child_tag_counts.keys()))
    outL('\n  plural_child_tags:', sorted(summary.plural_child_tags))
    outL('\n  all_child_tags:', sorted(summary.all_child_tags))


def write_code(args:Namespace, file:TextIO, summaries:Iterable[ElementSummary]) -> None:
  base = args.base

  def outL(*s:str) -> None:
    file.write(''.join(s))
    file.write('\n')

  #outL('# Generated by craft-xml-datatypes.')
  outL()
  outL('from __future__ import annotations')
  outL()
  outL('from dataclasses import dataclass, field')
  outL('from typing import ClassVar')
  #outL()
  outL('from pithy.xml.datatypes import ChildAttrInfo')
  outL()
  outL(f'from .base import {base}')
  outL()
  outL()

  for summary in summaries:
    write_class(args=args, outL=outL, summary=summary)

  outL()
  outL()
  outL(f'{base}._datatypes = {{')
  for summary in summaries:
    if summary.hint.is_list: continue
    outL(f'  {summary.tag!r}: {summary.name},')
  outL('}')


def write_class(args:Namespace, outL:Callable[...,None], summary:ElementSummary) -> None:

  if summary.hint.is_list: return

  base = args.base
  parent_hint = summary.hint.parent
  parent = class_name_for_tag(base, parent_hint) if parent_hint else base
  add_comments = bool(args.comment_examples)

  if tags := summary.all_child_tags:
    if len(tags) == 1:
      child_type = class_name_for_tag(base, single_el(tags))
    else:
      child_type = base
  else:
    child_type = None

  outL()
  outL()
  outL('@dataclass(kw_only=True)') # TODO: custom repr in XmlDatatype, set repr=False here.
  outL(f'class {summary.name}({parent}):', (f'# {summary.count} examples.' if add_comments else ''))
  outL(f'  _tag:ClassVar[str] = {summary.tag!r}')

  if summary.hint.child_attrs:
    outL()
    outL('  _child_attr_infos:ClassVar[dict[str,ChildAttrInfo]] = {')
    for tag, info in sorted(summary.hint.child_attrs.items()):
      outL(f'    {tag!r}: {info!r},')
    outL('  }')

  if summary.attrs:
    outL()
    attr_lines = sorted(fmt_attr_line(base, summary, raw_name, vals, comment_examples=args.comment_examples) for raw_name, vals in summary.attrs.items())
    for attr_line in attr_lines:
      outL(attr_line)

  if summary.single_child_tag_counts:
    outL()
    outL('  # single child tags: ', str(sorted(summary.single_child_tag_counts)))

  if summary.plural_child_tags:
    outL()
    outL('  # plural child tags: ', str(sorted(summary.plural_child_tags)))

  if child_type:
    outL()
    comment = repr(sorted(summary.all_child_tags)) if add_comments else ''
    outL(f'  ch:list[{child_type}] = field(default_factory=list) # {comment}')


def class_name_for_tag(base:str, tag:str) -> str:
  assert isinstance(tag, str), tag
  name = tag.replace('-', '_')
  return sanitize_for_py_keywords_and_type_names(base + name[0].upper() + name[1:])


def sanitize_attr(name:str) -> str:
  assert isinstance(name, str), name
  name = name.replace('-', '_')
  return sanitize_for_py_keywords_and_type_names(name[0].lower() + name[1:])


def fmt_attr_line(base:str, summary:ElementSummary, raw_name:str, vals:Counter[str], comment_examples:int) -> str:
  '''
  Create the code for a single attribute.
  '''
  name = ''

  try: info = summary.hint.child_attrs[raw_name]

  except KeyError: # Normal attribute.
    count = sum(vals.values())
    plain_type = guess_attr_type(vals) # The type before optionality inference.
    dflt = ''
    if count < summary.count: # Optional.
      attr_type = f'{plain_type}|None'
      dflt = 'None'
      if plain_type == 'bool': # Try to use a plain bool with default of the missing value.
        vals_set = set(bool_vals[v.lower()] for v in vals)
        if len(vals_set) == 1:
          dflt = repr(not vals_set.pop())
          attr_type = plain_type
    else:
      attr_type = plain_type

  else: # This attribute comes from a ChildAttrInfo.
    name = info.attr
    if info.is_plural or info.is_flattened:
      attr_type = f'list[{base}]' # TODO: needs to be more precise.
      dflt = 'field(default_factory=list)'
    else:
      attr_type = f'{base}|None' # TODO: needs to be more precise; may not be optional.
      dflt = 'None'
    count = summary.single_child_tag_counts[raw_name]

  if not name:
    name = sanitize_attr(raw_name)

  if comment_examples and vals:
    examples = dict(vals.most_common(comment_examples))
    examples_str = ', '.join(fmt_comment_item(val, count) for val, count in examples.items())
    suffix = '' if len(vals) <= comment_examples else f' +{len(vals) - comment_examples} more'
    comment = f' # {examples_str}{suffix}'
  else:
    comment = ''

  dflt_str = f' = {dflt}' if dflt else ''
  return f'  {name}:{attr_type}{dflt_str}{comment}'


def fmt_comment_item(val:str, count:int) -> str:
  t = truncate_repr_with_ellipsis(val, 64)
  if count == 1: return t
  else: return f'{t}*{count}'


def guess_attr_type(vals:Counter[str]) -> str:
  if all(int_re.fullmatch(v) for v in vals): return 'int'
  elif all(float_re.fullmatch(v) for v in vals): return 'float'
  elif all((v.lower() in bool_vals) for v in vals): return 'bool'
  return 'str'


int_re = re.compile(r'[+-]?[0-9]+')
float_re = re.compile(r'[+-]?[0-9]+\.?[0-9]*')


collection_types = {
  'list': list,
  'set': set,
  'tuple': tuple,
  'frozenset': frozenset,
}


if __name__ == '__main__': main()
