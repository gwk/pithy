# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Xml generated datatypes base class and utilities. See craft-xml-datatypes for context.
'''

from typing import Any, Callable, ClassVar, Iterable, Optional, Type, TypeVar, Union

from lxml.etree import Comment, _Element, fromstring as parse_xml_data

from ..py import sanitize_for_py_keywords
from ..transtruct import bool_vals


_T = TypeVar('_T')


_bool_cap_items:list[tuple[str,bool]] = [
  ('True', True),
  ('Yes', True),
  ('On', True),
  ('1', True),
  ('False', False),
  ('No', False),
  ('Off', False),
  ('0', False),
]


class XmlDatatype:
  '''
  Base class for all datatypes.
  '''

  _tag:ClassVar[str] # Static tag name set by all subclasses.

  _datatypes:ClassVar[dict[str,Type['XmlDatatype']]] # Static map of tag name to datatype class.

  _child_attr_tags:ClassVar[frozenset[str]] = frozenset(set())
  #^ Static dict of tag names for child element types that always appear singly.
  #^ These are mapped to attributes whose raw name is the same as the tag.


  @classmethod
  def _child_type(cls) -> Type['XmlDatatype']:
    'Static type of child element type, if all children are of the same type, or else the base type.'
    return XmlDatatype


  @classmethod
  def transtruct(cls, element:_Element) -> 'XmlDatatype':
    'Construct an instance from an lxml.etree element.'
    tag = element.tag
    if tag is Comment: tag = '!COMMENT'
    try: class_ = cls._datatypes[tag]
    except KeyError: raise ValueError(f'Unknown tag: {tag!r}')
    args:dict[str,Any] = {}
    for raw_name, raw_val in element.attrib.items():
      assert isinstance(raw_name, str)
      assert isinstance(raw_val, str)
      name = sanitize_for_py_keywords(raw_name.replace('-', '_'))
      t = class_._attr_type(name)
      try: # Convert the attribute string to the expected type.
        if t is bool: # Special handling for boolean names.
          v = bool_vals[raw_val]
        else:
          v = t(raw_val)
      except ValueError as e: raise ValueError(f'Invalid value for attribute: {name!r}; type: {t}; val: {raw_val!r}') from e
      args[name] = v

    children = []
    child_type = class_._child_type()
    for child_xml in element:
      child = child_type.transtruct(child_xml)
      if child._tag in class_._child_attr_tags:
        args[child._tag] = child # TODO: sanitize tag name.
      else:
        children.append(child)

    if children:
      assert 'children' not in args # TODO: deal with the potential for this key collision more thoroughly.
      args['children'] = children

    return class_(**args)


  @classmethod
  def parse(cls, name:str, data:bytes) -> 'XmlDatatype':
    doc = parse_xml_data(data)
    return cls.transtruct(doc)


  @classmethod
  def _attr_type(cls, name:str) -> Type:
    try: t:Type = cls.__annotations__[name]
    except KeyError as e: raise ValueError(f'Unknown attribute: {name!r}') from e
    if hasattr(t, '__origin__'):
      rtt = t.__origin__
      if rtt is Union:
        return t.__args__[0] # type: ignore # Note: this assumes that the type is an Optional.
      else:
        return t
    else: return t


  def walk(self, visitor:Callable[['XmlDatatype'],None]) -> None:
    '''
    Walk an xml datatype tree, calling visitor on each node.
    '''
    visitor(self)
    if hasattr(self, 'children'):
      for child in self.children: # type: ignore
        child.walk(visitor)


  def gen_walk(self, visitor:Callable[['XmlDatatype'],Optional[_T]]) -> Iterable[_T]:
    '''
    Walk an xml datatype tree and yield non-None results from visitor.
    '''
    print("WALK")
    result = visitor(self)
    if result is not None: yield result
    if hasattr(self, 'children'):
      for child in self.children: # type: ignore
        yield from child.gen_walk(visitor)



class XmlComment(XmlDatatype):
  '''
  A comment.
  '''
  _tag = "!COMMENT"
