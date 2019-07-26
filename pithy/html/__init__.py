# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Html type hierarchy.
'''

from html import escape as _escape
from inspect import signature as _signature
from typing import (Any, AnyStr as _AnyStr, Callable, Dict, Iterable, Iterator, List, NoReturn, Optional, Tuple, Type, TypeVar,
  Union, cast)

from ..exceptions import MultipleMatchesError, NoMatchError
from ..markup import Mu, MuAttrs, MuChild, _Mu, _MuChild
from . import semantics


DtDdPair = Tuple[List['Dt'],List['Dd']]


class HtmlNode(Mu):
  'Abstract HTML node; root class of the hierarchy. For the HTML tag, use `Html`.'

  void_elements = semantics.void_elements
  ws_sensitive_tags = semantics.ws_sensitive_elements
  tag_types:Dict[str,Type[Mu]] = {}

  @classmethod
  def parse(Class:Type[_Mu], source:_AnyStr, **kwargs:Any) -> _Mu:
    from html5_parser import parse
    if 'treebuilder' in kwargs: raise ValueError('HtmlNode.parse() requires default `lxml` treebuilder option.')
    if isinstance(source, bytes): kwargs['transport_encoding'] = 'utf-8'
    etree = parse(source, return_root=True, **kwargs)
    return Class.from_etree(etree)


  def esc_attr_val(self, val:str) -> str: return _escape(val, quote=True)

  def esc_text(self, text:str) -> str: return _escape(text, quote=False)

  @property
  def is_phrasing(self) -> bool:
    'Wether or not the node is phrasing content.'
    return False


  @property
  def attr_urls(self) -> Iterator[str]:
    yield from self.iter_visit(pre=_attr_urls_visit)


def _attr_urls_visit(node:HtmlNode) -> Iterator[str]:
  for k, v in node.attrs.items():
    if k in url_containing_attrs:
      if k == 'srcset':
        for el in v.split(','):
          src, space, descriptor = el.partition(' ')
          yield src
      else:
        yield v


url_containing_attrs = {
  'action', # Form URI.
  'cite',
  'data', # Object.
  'formaction',
  'href',
  'poster',
  'src',
  'srcset',
}


def _tag(Subclass:Type[_Mu]) -> Type[_Mu]:
  'Decorator for associating a concrete subclass with the lowercase tag matching its name.'
  assert issubclass(Subclass, Mu)
  Subclass.tag = Subclass.__name__.lower()
  HtmlNode.tag_types[Subclass.tag] = Subclass
  return Subclass


_Child = TypeVar('_Child', bound=Mu)
_Self = TypeVar('_Self', bound=Mu)

_Accessor = Callable[[_Self],_Child]

def _single(acc:_Accessor) -> _Accessor:
  'Wrapper function for creating a single-child accessor.'
  sig = _signature(acc)
  AccesseeClass:Type = sig.return_annotation
  tag = AccesseeClass.tag

  def html_single_accessor(self:_Self) -> _Child:
    for c in self.ch:
      if isinstance(c, Mu) and c.tag == tag: return cast(_Child, c)
    raise ValueError()
    return self.append(AccesseeClass())

  return property(html_single_accessor) # type: ignore


# Categories.

class HtmlEmbedded(HtmlNode):
  'Embedded content category.'


class HtmlFlow(HtmlNode):
  'Flow content category.'


class HtmlHeading(HtmlNode):
  'Heading content category.'


class HtmlInteractive(HtmlNode):
  'Interactive content category.'


class HtmlMetadata(HtmlNode):
  'Metadata content category: all node types that are metadata.'


class HtmlPalpable(HtmlNode):
  'Palbable content category.'


class HtmlPhrasing(HtmlNode):
  '''
  Phrasing content category: all node types that are phrasing content.
  Mnemonic: "If it can be inside a sentence, it's phrasing content."
  '''
  @property
  def is_phrasing(self) -> bool: return True # Note: this is overridden for certain special cases.


class HtmlSectioning(HtmlNode):
  'All node types that are sectioning content.'


class HtmlSectioningRoot(HtmlNode):
  'All node types that are sectioning roots.'


# Content models.

class HtmlNoContent(HtmlNode):
  '''
  Html elements that cannot have children.
  Note that the semantics of void elements are partially enforced here,
  and additionally via the set of tags in `.semantics.void_elements`.
  '''

  def append(self, child:_MuChild) -> _MuChild:
    raise TypeError(f'element cannot have child content: {self!r}')


class HtmlHeadingContent(HtmlNode):
  '''
  Heading content model: all node types that can contain heading elements.
  Note: this class represents <em: parents> of heading elements.
  The superclass of H1-H6 heading elemenents themselves is `Heading`.
  '''

  def h1(self, attrs:MuAttrs=None, ch:Iterable[MuChild]=(), cl:Iterable[str]=None,**kw_attrs:Any) -> 'H1':
    return self.append(H1(attrs=attrs, ch=ch, cl=cl, **kw_attrs))

  def h2(self, attrs:MuAttrs=None, ch:Iterable[MuChild]=(), cl:Iterable[str]=None,**kw_attrs:Any) -> 'H2':
    return self.append(H2(attrs=attrs, ch=ch, cl=cl, **kw_attrs))

  def h3(self, attrs:MuAttrs=None, ch:Iterable[MuChild]=(), cl:Iterable[str]=None,**kw_attrs:Any) -> 'H3':
    return self.append(H3(attrs=attrs, ch=ch, cl=cl, **kw_attrs))

  def h4(self, attrs:MuAttrs=None, ch:Iterable[MuChild]=(), cl:Iterable[str]=None,**kw_attrs:Any) -> 'H4':
    return self.append(H4(attrs=attrs, ch=ch, cl=cl, **kw_attrs))

  def h5(self, attrs:MuAttrs=None, ch:Iterable[MuChild]=(), cl:Iterable[str]=None,**kw_attrs:Any) -> 'H5':
    return self.append(H5(attrs=attrs, ch=ch, cl=cl, **kw_attrs))

  def h6(self, attrs:MuAttrs=None, ch:Iterable[MuChild]=(), cl:Iterable[str]=None,**kw_attrs:Any) -> 'H6':
    return self.append(H6(attrs=attrs, ch=ch, cl=cl, **kw_attrs))


class HtmlMetadataContent(HtmlNode):
  'Metadata content model: all node types that can contain metadata.'
  # TODO: metadata constructor methods.


class HtmlPhrasingContent(HtmlNode):
  '''
  Phrasing content model: all node types that can contain phrasing content.
  '''
  # TODO: all phrasing constructor methods.


class HtmlScriptSupporting(HtmlNode):

  def script(self, attrs:MuAttrs=None, ch:Iterable[MuChild]=(), cl:Iterable[str]=None,**kw_attrs:Any) -> 'Script':
    return self.append(Script(attrs=attrs, ch=ch, cl=cl, **kw_attrs))


class HtmlTextContent(HtmlNode):
  'All node types that can contain text content.'


class HtmlTransparentContent(HtmlNode):
  'Transparent content elements.'


class HtmlTransparentPhrasing(HtmlTransparentContent):
  'Nodes are considered phrasing content if all of their children are phrasing content.'
  @property
  def is_phrasing(self) -> bool:
    return all((not isinstance(c, Html) or c.is_phrasing) for c in self.ch)


class HtmlFlowContent(HtmlHeadingContent, HtmlPhrasingContent):
  '''
  All elements that can contain flow content (which is almost everything).
  '''
  # TODO: flow constructor methods.


# Elements.


@_tag
class A(HtmlFlow, HtmlInteractive, HtmlPalpable, HtmlPhrasing, HtmlTransparentContent):
  '''

  Categories:
    Interactive: if the element has an href attribute.

  Content model:
    Transparent: there must be no interactive content or a element descendants.

  Contexts for use: Phrasing.
  '''


@_tag
class Abbr(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''

  Contexts for use: Phrasing.
  '''


@_tag
class Address(HtmlFlow, HtmlPalpable, HtmlFlowContent):
  '''

  Content model:
    Flow: with no heading content descendants, no sectioning content descendants, and no header, footer, or address element descendants.

  Contexts for use: Flow.
  '''


@_tag
class Area(HtmlFlow, HtmlPhrasing, HtmlNoContent):
  '''

  Contexts for use: Where phrasing content is expected, but only if there is a map element ancestor.
  '''


@_tag
class Article(HtmlFlow, HtmlPalpable, HtmlSectioning, HtmlFlowContent):
  '''

  Contexts for use: Flow.
  '''


@_tag
class Aside(HtmlFlow, HtmlPalpable, HtmlSectioning, HtmlFlowContent):
  '''

  Contexts for use: Flow.
  '''


@_tag
class Audio(HtmlEmbedded, HtmlFlow, HtmlInteractive, HtmlPalpable, HtmlPhrasing):
  '''

  Categories:
    Interactive: if the element has a controls attribute.
    Palpable: if the element has a controls attribute.

  Content model:
    Zero or more source elements, then zero or more track elements, then transparent, but with no media element descendants: if the element does not have a src attribute.
    Zero or more track elements, then transparent, but with no media element descendants: if the element has a src attribute.

  Contexts for use: Embedded.
  '''


@_tag
class B(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''

  Contexts for use: Phrasing.
  '''


@_tag
class Base(HtmlMetadata, HtmlNoContent):
  '''

  Contexts for use: In a head element containing no other base elements.
  '''


@_tag
class Bdi(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''

  Contexts for use: Phrasing.
  '''


@_tag
class Bdo(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''

  Contexts for use: Phrasing.
  '''


@_tag
class Blockquote(HtmlFlow, HtmlPalpable, HtmlSectioningRoot, HtmlFlowContent):
  '''

  Contexts for use: Flow.
  '''


@_tag
class Body(HtmlSectioningRoot, HtmlFlowContent):
  '''

  Contexts for use: As the second element in an html element.
  '''


@_tag
class Br(HtmlFlow, HtmlPhrasing, HtmlNoContent):
  '''

  Contexts for use: Phrasing.
  '''


@_tag
class Button(HtmlFlow, HtmlInteractive, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''

  Categories:
    Listed, labelable, submittable, and autocapitalize-inheriting form-associated element: None.

  Content model:
    Phrasing: there must be no interactive content descendant.

  Contexts for use: Phrasing.
  '''


@_tag
class Canvas(HtmlEmbedded, HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlTransparentContent):
  '''

  Content model:
    Transparent: with no interactive content descendants except for a elements, img elements with usemap attributes, button elements, input elements whose type attribute are in the Checkbox or Radio Button states, input elements that are buttons, select elements with a multiple attribute or a display size greater than 1, and elements that would not be interactive content except for having the tabindex attribute specified.

  Contexts for use: Embedded.
  '''


@_tag
class Caption(HtmlFlowContent):
  '''

  Content model:
    Flow: with no descendant table elements.

  Contexts for use: As the first element child of a table element.
  '''


@_tag
class Cite(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''

  Contexts for use: Phrasing.
  '''


@_tag
class Code(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''

  Contexts for use: Phrasing.
  '''


@_tag
class Col(HtmlNoContent):
  '''

  Contexts for use: As a child of a colgroup element that doesn't have a span attribute.
  '''


@_tag
class Colgroup(HtmlNode):
  '''

  Content model:
    No: if the span attribute is present.
    Zero or more col and template elements: if the span attribute is absent.

  Contexts for use: As a child of a table element, after any caption elements and before any thead, tbody, tfoot, and tr elements.
  '''


@_tag
class Data(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''

  Contexts for use: Phrasing.
  '''


@_tag
class Datalist(HtmlFlow, HtmlPhrasing):
  '''

  Content model:
    Either: phrasing: None.
    Or: Zero or more option and script-supporting elements: None.

  Contexts for use: Phrasing.
  '''


@_tag
class Dd(HtmlFlowContent):
  '''

  Contexts for use: After dt or dd elements inside div elements that are children of a dl element, After dt or dd elements inside dl elements.
  '''


@_tag
class Del(HtmlFlow, HtmlPhrasing, HtmlTransparentContent):
  '''

  Contexts for use: Phrasing.
  '''


@_tag
class Details(HtmlFlow, HtmlInteractive, HtmlPalpable, HtmlSectioningRoot):
  '''

  Content model:
    One summary element followed by flow: None.

  Contexts for use: Flow.
  '''
  # TODO: summary property.


@_tag
class Dfn(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''

  Content model:
    Phrasing: there must be no dfn element descendants.

  Contexts for use: Phrasing.
  '''

  def dfn(self) -> NoReturn: raise TypeError('`dfn` elements cannot have `dfn` descendants.')


@_tag
class Dialog(HtmlFlow, HtmlSectioningRoot, HtmlFlowContent):
  '''

  Contexts for use: Flow.
  '''


@_tag
class Div(HtmlFlow, HtmlPalpable, HtmlFlowContent):
  '''

  Content model:
    Flow: if the element is not a child of a dl element.
    One or more dt elements followed by one or more dd elements, optionally intermixed with script-supporting elements: if the element is a child of a dl element.

  Contexts for use: As a child of a dl element, Flow.
  '''


@_tag
class Dl(HtmlFlow, HtmlPalpable):
  '''

  Categories:
    Palpable: if the element's children include at least one name-value group.

  Content model:
    Either: Zero or more groups each consisting of one or more dt elements followed by one or more dd elements, optionally intermixed with script-supporting elements: None.
    Or: One or more div elements, optionally intermixed with script-supporting elements: None.

  Contexts for use: Flow.
  '''

  @property
  def dt_dd_groups(self) -> Iterable[Union[Div,DtDdPair]]:
    pair:Optional[DtDdPair] = None
    for c in self.child_nodes():
      if isinstance(c, Div):
        yield c
      elif isinstance(c, Dt):
        if pair:
          if pair[1]: # Yield previous pair and start new one.
            yield pair
            pair = ([c], [])
          else: # Accumulate additional Dt.
            pair[0].append(c)
            continue
        else:
          pair = ([c], [])
      elif isinstance(c, Dd):
        if pair:
          pair[1].append(c) # Accumulate additional Dt.
        else: # This case is invalid, but we can create a pair with no leading Dt.
          pair = ([], [c])
    if pair: yield pair


@_tag
class Dt(HtmlFlowContent):
  '''

  Content model:
    Flow: with no header, footer, sectioning content, or heading content descendants.

  Contexts for use: Before dd or dt elements inside div elements that are children of a dl element, Before dd or dt elements inside dl elements.
  '''


@_tag
class Em(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''

  Contexts for use: Phrasing.
  '''


@_tag
class Embed(HtmlEmbedded, HtmlFlow, HtmlInteractive, HtmlPalpable, HtmlPhrasing, HtmlNoContent):
  '''

  Contexts for use: Embedded.
  '''


@_tag
class Fieldset(HtmlFlow, HtmlPalpable, HtmlSectioningRoot):
  '''

  Categories:
    Listed and autocapitalize-inheriting form-associated element: None.

  Content model:
    Optionally a legend element, followed by flow: None.

  Contexts for use: Flow.
  '''


@_tag
class Figcaption(HtmlFlowContent):
  '''

  Contexts for use: As the first or last child of a figure element.
  '''


@_tag
class Figure(HtmlFlow, HtmlPalpable, HtmlSectioningRoot):
  '''

  Content model:
    Either: one figcaption element followed by flow: None.
    Or: flow: None.
    Or: flow content followed by one figcaption element: None.

  Contexts for use: Flow.
  '''


@_tag
class Footer(HtmlFlow, HtmlPalpable, HtmlFlowContent):
  '''

  Content model:
    Flow: with no header or footer element descendants.

  Contexts for use: Flow.
  '''


@_tag
class Form(HtmlFlow, HtmlPalpable, HtmlFlowContent):
  '''

  Content model:
    Flow: with no form element descendants.

  Contexts for use: Flow.
  '''


class Heading(HtmlPhrasingContent):
  '''
  'Parent class for H1-H6 heading elements.

  Contexts for use: As a child of an hgroup element, Flow.
  '''

  @classmethod
  def for_level(cls, level:int, *, attrs:MuAttrs=None, ch:Iterable[MuChild]=(), cl:Iterable[str]=None, **kw_attrs:Any) -> 'Heading':
    c = _heading_classes[min(level, 6) - 1]
    return c(attrs=attrs, ch=ch, cl=cl, **kw_attrs)


@_tag
class H1(Heading):
  ''

@_tag
class H2(Heading):
  ''

@_tag
class H3(Heading):
  ''

@_tag
class H4(Heading):
  ''

@_tag
class H5(Heading):
  ''

@_tag
class H6(Heading):
  ''

_heading_classes:List[Type[Heading]] = [H1, H2, H3, H4, H5, H6]


@_tag
class Head(HtmlMetadataContent):
  '''

  Content model:
    Zero or more elements of metadata content, of which no more than one is a title element and no more than one is a base element: if the document is an iframe srcdoc document or if title information is available from a higher-level protocol.
    One or more elements of metadata content, of which exactly one is a title element and no more than one is a base element: Otherwise.

  Contexts for use: As the first element in an html element.
  '''

  @property
  def title(self) -> 'Title': return self._single(Title)

  def add_stylesheet(self, url:str, media='all') -> None:
    self.append(Link(rel='stylesheet', type='text/css', media=media, href=url))


@_tag
class Header(HtmlFlow, HtmlPalpable, HtmlFlowContent):
  '''

  Content model:
    Flow: with no header or footer element descendants.

  Contexts for use: Flow.
  '''


@_tag
class Hgroup(HtmlFlow, HtmlHeading, HtmlPalpable):
  '''

  Content model:
    One or more h1, h2, h3, h4, h5, h6 elements, optionally intermixed with script-supporting elements: None.

  Contexts for use: Flow.
  '''


@_tag
class Hr(HtmlFlow, HtmlNoContent):
  '''

  Contexts for use: Flow.
  '''


@_tag
class Html(HtmlNode):
  '''

  Content model:
    A head element followed by a body element: None.

  Contexts for use: As document's document element, Wherever a subdocument fragment is allowed in a compound document.
  '''

  def render(self, newline:bool=True) -> Iterator[str]:
    yield '<!DOCTYPE html>\n'
    yield from super().render(newline=newline)

  @property
  def body(self) -> Body: return self._single(Body)

  @property
  def head(self) -> Head: return self._single(Head)

  @staticmethod
  def doc(*, title:str, charset='utf-8', lang='en') -> 'Html':
    html = Html(lang=lang)
    head = html.head
    head.title.append(title)
    head.append(Meta(charset=charset))
    return html


@_tag
class I(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''

  Contexts for use: Phrasing.
  '''


@_tag
class Iframe(HtmlEmbedded, HtmlFlow, HtmlInteractive, HtmlPalpable, HtmlPhrasing, HtmlNoContent):
  '''

  Contexts for use: Embedded.
  '''


@_tag
class Img(HtmlEmbedded, HtmlFlow, HtmlInteractive, HtmlPalpable, HtmlPhrasing, HtmlNoContent):
  '''

  Categories:
    Form-associated element: None.
    Interactive: if the element has a usemap attribute.

  Contexts for use: Embedded.
  '''


@_tag
class Input(HtmlFlow, HtmlInteractive, HtmlPalpable, HtmlPhrasing, HtmlNoContent):
  '''

  Categories:
    Interactive: if the type attribute is not in the hidden state.
    Listed, labelable, submittable, resettable, and autocapitalize-inheriting form-associated element: if the type attribute is not in the hidden state.
    Listed, submittable, resettable, and autocapitalize-inheriting form-associated element: if the type attribute is in the hidden state.
    Palpable: if the type attribute is not in the hidden state.

  Contexts for use: Phrasing.
  '''


@_tag
class Ins(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlTransparentContent):
  '''

  Contexts for use: Phrasing.
  '''


@_tag
class Kbd(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''

  Contexts for use: Phrasing.
  '''


@_tag
class Label(HtmlFlow, HtmlInteractive, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''

  Content model:
    Phrasing: with no descendant labelable elements unless it is the element's labeled control, and no descendant label elements.

  Contexts for use: Phrasing.
  '''


@_tag
class Legend(HtmlPhrasingContent):
  '''

  Contexts for use: As the first child of a fieldset element.
  '''


@_tag
class Li(HtmlFlowContent):
  '''

  Contexts for use: Inside menu elements, Inside ol elements, Inside ul elements.
  '''


@_tag
class Link(HtmlFlow, HtmlMetadata, HtmlPhrasing, HtmlNoContent):
  '''

  Categories:
    Flow: if the element is allowed in the body.
    Phrasing: if the element is allowed in the body.

  Contexts for use: If the element is allowed in the body: where phrasing content is expected, In a noscript element that is a child of a head element, Where metadata content is expected.
  '''


@_tag
class Main(HtmlFlow, HtmlPalpable, HtmlFlowContent):
  '''

  Contexts for use: Where flow content is expected, but only if it is a hierarchically correct main element.
  '''


@_tag
class Map(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlTransparentContent):
  '''

  Contexts for use: Phrasing.
  '''


@_tag
class Mark(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''

  Contexts for use: Phrasing.
  '''


@_tag
class Math(HtmlNode):
  '''

  Contexts for use: .
  '''


@_tag
class Menu(HtmlFlow, HtmlPalpable):
  '''

  Categories:
    Palpable: if the element's children include at least one li element.

  Content model:
    Zero or more li and script-supporting elements: None.

  Contexts for use: Flow.
  '''


@_tag
class Meta(HtmlFlow, HtmlMetadata, HtmlPhrasing, HtmlNoContent):
  '''

  Categories:
    Flow: if the itemprop attribute is present.
    Phrasing: if the itemprop attribute is present.

  Contexts for use: If the charset attribute is present, or if the element's http-equiv attribute is in the Encoding declaration state: in a head element, If the http-equiv attribute is present but not in the Encoding declaration state: in a head element, If the http-equiv attribute is present but not in the Encoding declaration state: in a noscript element that is a child of a head element, If the itemprop attribute is present: where metadata content is expected, If the itemprop attribute is present: where phrasing content is expected, If the name attribute is present: where metadata content is expected.
  '''


@_tag
class Meter(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''

  Categories:
    Labelable element: None.

  Content model:
    Phrasing: there must be no meter element descendants.

  Contexts for use: Phrasing.
  '''


@_tag
class Nav(HtmlFlow, HtmlPalpable, HtmlSectioning, HtmlFlowContent):
  '''

  Contexts for use: Flow.
  '''


@_tag
class Noscript(HtmlFlow, HtmlMetadata, HtmlPhrasing):
  '''

  Content model:
    Otherwise: text that conforms to the requirements given in the prose: None.
    When scripting is disabled, in a head element: in any order, zero or more link elements, zero or more style elements, and zero or more meta elements: None.
    When scripting is disabled, not in a head element: transparent: there must be no noscript element descendants.

  Contexts for use: In a head element of an HTML document, if there are no ancestor noscript elements, Where phrasing content is expected in HTML documents, if there are no ancestor noscript elements.
  '''


@_tag
class Object(HtmlEmbedded, HtmlFlow, HtmlInteractive, HtmlPalpable, HtmlPhrasing):
  '''

  Categories:
    Interactive: if the element has a usemap attribute.
    Listed and submittable form-associated element: None.

  Content model:
    Zero or more param elements, then, transparent: None.

  Contexts for use: Embedded.
  '''


@_tag
class Ol(HtmlFlow, HtmlPalpable):
  '''

  Categories:
    Palpable: if the element's children include at least one li element.

  Content model:
    Zero or more li and script-supporting elements: None.

  Contexts for use: Flow.
  '''


@_tag
class Optgroup(HtmlNode):
  '''

  Content model:
    Zero or more option and script-supporting elements: None.

  Contexts for use: As a child of a select element.
  '''


@_tag
class Option(HtmlTextContent):
  '''

  Content model:
    No: if the element has a label attribute and a value attribute.
    Text: if the element has a label attribute but no value attribute.
    Text: if the element has no label attribute and is a child of a datalist element.
    Text that is not inter-element whitespace: if the element has no label attribute and is not a child of a datalist element.

  Contexts for use: As a child of a datalist element, As a child of a select element, As a child of an optgroup element.
  '''


@_tag
class Output(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''

  Categories:
    Listed, labelable, resettable, and autocapitalize-inheriting form-associated element: None.

  Contexts for use: Phrasing.
  '''


@_tag
class P(HtmlFlow, HtmlPalpable, HtmlPhrasingContent):
  '''

  Contexts for use: Flow.
  '''


@_tag
class Param(HtmlNoContent):
  '''

  Contexts for use: As a child of an object element, before any flow content.
  '''


@_tag
class Picture(HtmlEmbedded, HtmlFlow, HtmlPhrasing):
  '''

  Content model:
    Zero or more source elements, followed by one img element, optionally intermixed with script-supporting elements: None.

  Contexts for use: Embedded.
  '''


@_tag
class Pre(HtmlFlow, HtmlPalpable, HtmlPhrasingContent):
  '''

  Contexts for use: Flow.
  '''


@_tag
class Progress(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''

  Categories:
    Labelable element: None.

  Content model:
    Phrasing: there must be no progress element descendants.

  Contexts for use: Phrasing.
  '''


@_tag
class Q(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''

  Contexts for use: Phrasing.
  '''


@_tag
class Rp(HtmlTextContent):
  '''

  Contexts for use: As a child of a ruby element, either immediately before or immediately after an rt element.
  '''


@_tag
class Rt(HtmlPhrasingContent):
  '''

  Contexts for use: As a child of a ruby element.
  '''


@_tag
class Ruby(HtmlFlow, HtmlPalpable, HtmlPhrasing):
  '''

  Content model:
    See prose: None.

  Contexts for use: Phrasing.
  '''


@_tag
class S(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''

  Contexts for use: Phrasing.
  '''


@_tag
class Samp(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''

  Contexts for use: Phrasing.
  '''


@_tag
class Script(HtmlFlow, HtmlMetadata, HtmlPhrasing):
  '''

  Categories:
    Script-supporting element: None.

  Content model:
    : if there is a src attribute, the element must be either empty or contain only script documentation that also matches script content restrictions.
    : if there is no src attribute, depends on the value of the type attribute, but must match script content restrictions.

  Contexts for use: Phrasing, Where metadata content is expected, Where script-supporting elements are expected.
  '''


@_tag
class Section(HtmlFlow, HtmlPalpable, HtmlSectioning, HtmlFlowContent):
  '''

  Contexts for use: Flow.
  '''

  @property
  def heading(self) -> Optional[HtmlNode]:
    for el in self.ch:
      if isinstance(el, str) and (not el or el.isspace()): continue
      if isinstance(el, Heading): return el
    return None


@_tag
class Select(HtmlFlow, HtmlInteractive, HtmlPalpable, HtmlPhrasing):
  '''

  Categories:
    Listed, labelable, submittable, resettable, and autocapitalize-inheriting form-associated element: None.

  Content model:
    Zero or more option, optgroup, and script-supporting elements: None.

  Contexts for use: Phrasing.
  '''


@_tag
class Slot(HtmlFlow, HtmlPhrasing, HtmlTransparentContent):
  '''

  Contexts for use: Phrasing.
  '''


@_tag
class Small(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''

  Contexts for use: Phrasing.
  '''


@_tag
class Source(HtmlNoContent):
  '''

  Contexts for use: As a child of a media element, before any flow content or track elements, As a child of a picture element, before the img element.
  '''


@_tag
class Span(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''

  Contexts for use: Phrasing.
  '''


@_tag
class Strong(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''

  Contexts for use: Phrasing.
  '''


@_tag
class Style(HtmlMetadata):
  '''

  Content model:
    Text that gives a conformant style sheet: None.

  Contexts for use: In a noscript element that is a child of a head element, Where metadata content is expected.
  '''


@_tag
class Sub(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''

  Contexts for use: Phrasing.
  '''


@_tag
class Summary(HtmlPhrasing):
  '''

  Content model:
    Either: phrasing: None.
    Or: one element of heading: None.

  Contexts for use: As the first child of a details element.
  '''


@_tag
class Sup(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''

  Contexts for use: Phrasing.
  '''


@_tag
class Svg(HtmlNode):
  '''

  Contexts for use: .
  '''


@_tag
class Table(HtmlFlow, HtmlPalpable):
  '''

  Content model:
    In this order: optionally a caption element, followed by zero or more colgroup elements, followed optionally by a thead element, followed by either zero or more tbody elements or one or more tr elements, followed optionally by a tfoot element, optionally intermixed with one or more script-supporting elements: None.

  Contexts for use: Flow.
  '''
  # TODO: def caption



@_tag
class Tbody(HtmlNode):
  '''

  Content model:
    Zero or more tr and script-supporting elements: None.

  Contexts for use: As a child of a table element, after any caption, colgroup, and thead elements, but only if there are no tr elements that are children of the table element.
  '''


@_tag
class Td(HtmlSectioningRoot, HtmlFlowContent):
  '''

  Contexts for use: As a child of a tr element.
  '''


@_tag
class Template(HtmlFlow, HtmlMetadata, HtmlPhrasing):
  '''

  Categories:
    Script-supporting element: None.

  Content model:
    Nothing (for clarification, see example): None.

  Contexts for use: As a child of a colgroup element that doesn't have a span attribute, Phrasing, Where metadata content is expected, Where script-supporting elements are expected.
  '''


@_tag
class Textarea(HtmlFlow, HtmlInteractive, HtmlPalpable, HtmlPhrasing, HtmlTextContent):
  '''

  Categories:
    Listed, labelable, submittable, resettable, and autocapitalize-inheriting form-associated element: None.

  Contexts for use: Phrasing.
  '''


@_tag
class Tfoot(HtmlNode):
  '''

  Content model:
    Zero or more tr and script-supporting elements: None.

  Contexts for use: As a child of a table element, after any caption, colgroup, thead, tbody, and tr elements, but only if there are no other tfoot elements that are children of the table element.
  '''


@_tag
class Th(HtmlFlowContent):
  '''

  Content model:
    Flow: with no header, footer, sectioning content, or heading content descendants.

  Contexts for use: As a child of a tr element.
  '''


@_tag
class Thead(HtmlNode):
  '''

  Content model:
    Zero or more tr and script-supporting elements: None.

  Contexts for use: As a child of a table element, after any caption, and colgroup elements and before any tbody, tfoot, and tr elements, but only if there are no other thead elements that are children of the table element.
  '''


@_tag
class Time(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''

  Content model:
    Otherwise: Text: must match requirements described in prose below.
    Phrasing: if the element has a datetime attribute.

  Contexts for use: Phrasing.
  '''


@_tag
class Title(HtmlMetadata):
  '''

  Content model:
    Text that is not inter-element whitespace: None.

  Contexts for use: In a head element containing no other title elements.
  '''


@_tag
class Tr(HtmlNode):
  '''

  Content model:
    Zero or more td, th, and script-supporting elements: None.

  Contexts for use: As a child of a table element, after any caption, colgroup, and thead elements, but only if there are no tbody elements that are children of the table element, As a child of a tbody element, As a child of a tfoot element, As a child of a thead element.
  '''


@_tag
class Track(HtmlNoContent):
  '''

  Contexts for use: As a child of a media element, before any flow content.
  '''


@_tag
class U(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''

  Contexts for use: Phrasing.
  '''


@_tag
class Ul(HtmlFlow, HtmlPalpable):
  '''

  Categories:
    Palpable: if the element's children include at least one li element.

  Content model:
    Zero or more li and script-supporting elements: None.

  Contexts for use: Flow.
  '''


@_tag
class Var(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''

  Contexts for use: Phrasing.
  '''


@_tag
class Video(HtmlEmbedded, HtmlFlow, HtmlInteractive, HtmlPalpable, HtmlPhrasing):
  '''

  Categories:
    Interactive: if the element has a controls attribute.

  Content model:
    Zero or more source elements, then zero or more track elements, then transparent, but with no media element descendants: if the element does not have a src attribute.
    Zero or more track elements, then transparent, but with no media element descendants: if the element has a src attribute.

  Contexts for use: Embedded.
  '''


@_tag
class Wbr(HtmlFlow, HtmlPhrasing, HtmlNoContent):
  '''

  Contexts for use: Phrasing.
  '''
