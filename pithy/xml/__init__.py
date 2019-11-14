# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Xml type.
'''

from typing import Any, Iterable, List, Union
from xml.etree.ElementTree import Element
from xml.sax.saxutils import escape as _escape_text, quoteattr as _escape_attr

from ..exceptions import MultipleMatchesError, NoMatchError
from ..markup import Mu, MuAttrItem, MuAttrs, MuChild, _Mu


#from ..desc import repr_lim
#from ..exceptions import DeleteNode, FlattenNode, MultipleMatchesError, NoMatchError, ConflictingValues
#from .escape import fmt_attr_items

XmlAttrs = MuAttrs
XmlAttrItem = MuAttrItem

XmlChild = Union[str,'Xml']
XmlChildren = List[XmlChild]


class XmlNode(Mu):
  '''
  Xml subclass adds XML-specific details to Mu base type.
  '''

  def esc_attr_val(self, val:str) -> str: return _escape_attr(val)

  def esc_text(self, text:str) -> str: return _escape_text(text) # Ignoring custom entities for now.


class Xml(Mu):
  '''
  Generic Xml node that contains its own tag.
  '''
  __slots__ = ('tag')

  def __init__(self:_Mu, *, tag, attrs:MuAttrs=None, ch:Iterable[MuChild]=(), cl:Iterable[str]=None,
   _orig:_Mu=None, _parent:'Mu'=None, **kw_attrs:Any) -> None:
    self.tag = tag
    super().__init__(tag=tag, attrs=attrs, ch=ch, cl=cl, _orig=_orig, _parent=_parent, **kw_attrs) # type: ignore
