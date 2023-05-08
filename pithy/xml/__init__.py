# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Xml Mu/markup type.
'''

from typing import Any, Iterable, List, Optional, Union

from ..markup import _Mu, Mu, MuAttrs, MuChildOrChildrenLax


XmlChild = Union[str,'Xml']
XmlChildren = List[XmlChild]


class XmlNode(Mu):
  '''
  Xml subclass adds XML-specific details to Mu base type.
  '''


class Xml(Mu):
  '''
  Generic Xml node that contains its own tag.
  '''
  __slots__ = ('tag')

  def __init__(self:_Mu, *,
   tag:str,
   attrs:MuAttrs|None=None,
   _:MuChildOrChildrenLax=(),
   cl:Iterable[str]|None=None,
   _orig:_Mu|None=None,
   _parent:Optional['Mu']=None,
   **kw_attrs:Any) -> None:
    super().__init__(tag=tag, attrs=attrs, _=_, cl=cl, _orig=_orig, _parent=_parent, **kw_attrs)
