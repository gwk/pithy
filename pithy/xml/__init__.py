# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Xml Mu/markup type.
'''

from typing import Any, Iterable, List, Union

from ..markup import Mu, MuAttrs, MuChild, _Mu

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

  def __init__(self:_Mu, *, tag, attrs:MuAttrs=None, ch:Iterable[MuChild]=(), cl:Iterable[str]=None,
   _orig:_Mu=None, _parent:'Mu'=None, **kw_attrs:Any) -> None:
    super().__init__(tag=tag, attrs=attrs, ch=ch, cl=cl, _orig=_orig, _parent=_parent, **kw_attrs)
