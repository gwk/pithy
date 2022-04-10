# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Base class and utilities for generated Xml datatypes; see the craft-xml-datatypes script for context.
'''

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, ClassVar, Iterable, Optional, Type, TypeVar

from ..transtruct import Transtructor



_T = TypeVar('_T')


@dataclass
class ChildAttrInfo:
  '''
  Information about a child tag that is treated as an attribute.
  '''
  attr:str = ''
  is_plural:bool = False # If set, then the attribute accumulates multiple children into the attribute list.
  is_flattened:bool = False # If set, then the child node's children are used as the value; its attributes are ignored.


class XmlDatatype:
  '''
  Base class for all Xml datatypes.
  '''

  _tag:ClassVar[str] # Static tag name set by all subclasses.

  _datatypes:ClassVar[dict[str,Type[XmlDatatype]]] # Static map of tag name to datatype class.

  _child_attr_infos:ClassVar[dict[str,ChildAttrInfo]] = {}
  #^ Static dict of child tag names to info for child element types that always appear singly.
  #^ These are mapped to attributes whose raw name is the same as the tag.


  def visit(self, *, pre:Optional[Callable[[XmlDatatype],None]]=None, post:Optional[Callable[[XmlDatatype],None]]=None) -> None:
    '''
    Visit the data tree, calling pre and post on each node.
    TODO: factor this out with markup.visit.
    '''
    if pre is not None: pre(self)
    try: ch = getattr(self, 'children')
    except AttributeError: pass
    else:
      for child in ch:
        child.walk(pre, post)
    if post is not None: post(self)


  def gen_visit(self, *,
   pre:Optional[Callable[[XmlDatatype],Optional[_T]]]=None,
   post:Optional[Callable[[XmlDatatype],Optional[_T]]]=None) -> Iterable[_T]:
    '''
    Visit the data tree, yielding Walk an xml datatype tree and yield non-None results from visitor
    TODO: reconcile and factor out with markup.iter_visit. Perhaps gen_visit and iter_visit both exist, but need better names.
    '''
    if pre is not None:
      if result := pre(self): yield result
    if hasattr(self, 'ch'):
      for child in self.ch: # type: ignore
        yield from child.gen_visit(pre=pre, post=post)
    if post is not None:
      if result := post(self): yield result



class XmlComment(XmlDatatype):
  '''
  An XML comment.
  '''
  _tag = "!COMMENT"



xmlTranstructor = Transtructor()

@xmlTranstructor.selector(XmlDatatype)
def xml_selector(class_:type[XmlDatatype], val:dict) -> type:
  #print("xml_selector:", class_, val[''])
  return class_._datatypes[val['']]


@xmlTranstructor.prefigure(XmlDatatype)
def xml_prefigure(class_:type[XmlDatatype], val:dict) -> dict:
  '''
  Prefigure a dict of raw xml data.
  '''

  if child_attr_infos := class_._child_attr_infos:
    # Pull children out of the child array as necessary.
    try: ch = val['ch']
    except KeyError: pass
    else:
      clean_ch = []
      for child in ch:
        if not isinstance(child, dict):
          clean_ch.append(child)
          continue
        tag = child['']
        try: info = child_attr_infos[tag]
        except KeyError:
          clean_ch.append(child)
          continue
        attr = info.attr
        assert attr
        if info.is_plural:
          try: coll = val[attr]
          except KeyError: coll = val[attr] = []
          if info.is_flattened:
            coll.extend(child['ch'])
          else:
            coll.append(child)
        else:
          assert attr not in val
          val[attr] = child
      if clean_ch:
        val['ch'] = clean_ch
      else:
        del val['ch']

  return val
