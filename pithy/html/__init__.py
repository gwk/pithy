# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Html type hierarchy.
'''

from html import escape as _escape
from inspect import signature as _signature
from typing import (Any, AnyStr as _AnyStr, Callable, Dict, Iterable, Iterator, List, NoReturn, Optional, Tuple, Type, TypeVar,
  Union, cast)

from ..exceptions import MultipleMatchesError, NoMatchError
from ..markup import Mu, MuAttrs, MuChild, _Mu
from . import semantics


DtDdPair = Tuple[List['Dt'],List['Dd']]


class HtmlNode(Mu):
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

  def xml_accessor(self:_Self) -> _Child:
    for c in self.ch:
      if isinstance(c, Mu) and c.tag == tag: return cast(_Child, c)
    raise ValueError()
    return self.append(AccesseeClass())

  return property(xml_accessor) # type: ignore


class HtmlFlow(HtmlNode):
  'Flow content model.'


class HtmlHeading(HtmlNode):

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


class HtmlPhrasing(HtmlNode):
  'Phrasing content model.'


class HtmlScriptSupporting(HtmlNode):

  def script(self, attrs:MuAttrs=None, ch:Iterable[MuChild]=(), cl:Iterable[str]=None,**kw_attrs:Any) -> 'Script':
    return self.append(Script(attrs=attrs, ch=ch, cl=cl, **kw_attrs))


class HtmlTransparent(HtmlNode):
  'Transparent content model.'


@_tag
class A(HtmlTransparent):
  '''
  Transparent, but there must be no interactive content or a element descendants.
  '''

@_tag
class Abbr(HtmlPhrasing):
  ''

@_tag
class Address(HtmlFlow):
  '''
  Flow content, but with no heading content descendants, no sectioning content descendants, and no header, footer, or address element descendants.
  '''

@_tag
class Area(HtmlFlow):
  'Flow content, if it is a descendant of a map element.'

@_tag
class Article(HtmlFlow):
  ''

@_tag
class Aside(HtmlFlow):
  ''

@_tag
class B(HtmlPhrasing):
  ''

@_tag
class Base(HtmlNode):
  'Content model: nothing.'

@_tag
class Bdi(HtmlPhrasing):
  ''

@_tag
class Bdo(HtmlPhrasing):
  ''

@_tag
class Blockquote(HtmlFlow):
  ''

@_tag
class Body(HtmlFlow):
  ''

@_tag
class Br(HtmlNode):
  'Content model: nothing.'
  ''

@_tag
class Button(HtmlFlow):
  ''

@_tag
class Canvas(HtmlTransparent):
  '''
  Transparent, but with no interactive content descendants
  except for <a> elements, <button> elements, <input> elements whose type attribute is checkbox, radio, or button.
  '''

@_tag
class Caption(HtmlFlow):
  'Flow content, but with no descendant table elements.'

@_tag
class Cite(HtmlPhrasing):
  ''

@_tag
class Code(HtmlPhrasing):
  ''

@_tag
class Col(HtmlNode):
  'Nothing.'

@_tag
class Colgroup(HtmlNode):
  'If the span attribute is present: Nothing.'

@_tag
class Data(HtmlPhrasing):
  ''

@_tag
class Datalist(HtmlNode):
  ''

@_tag
class Dd(HtmlFlow):
  ''

@_tag
class Del(HtmlTransparent):
  ''

@_tag
class Details(HtmlFlow):
  'One summary element followed by flow content.'


@_tag
class Dfn(HtmlPhrasing):
  'Phrasing content, but there must be no dfn element descendants.'

  def dfn(self) -> NoReturn: raise TypeError('`dfn` elements cannot have `dfn` descendants.')


@_tag
class Dialog(HtmlFlow):
  ''

@_tag
class Div(HtmlNode):
  ''

@_tag
class Dl(HtmlNode):
  '''
  Either: Zero or more groups each consisting of one or more dt elements followed by one or more dd elements,
  optionally intermixed with script-supporting elements.
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
class Dt(HtmlFlow):
  '''
  Flow content, but with no header, footer, sectioning content, or heading content descendants.
  '''

@_tag
class Em(HtmlPhrasing):
  ''

@_tag
class Embed(HtmlNode):
  ''

@_tag
class Fieldset(HtmlNode):
  ''

@_tag
class Figcaption(HtmlFlow):
  ''

@_tag
class Figure(HtmlFlow):
  'Either: one figcaption element followed by flow content.'

@_tag
class Footer(HtmlFlow):
  'Flow content, but with no header or footer element descendants.'

@_tag
class Form(HtmlFlow):
  'Flow content, but with no form element descendants.'

@_tag
class H1(HtmlPhrasing):
  ''

@_tag
class H2(HtmlPhrasing):
  ''

@_tag
class H3(HtmlPhrasing):
  ''

@_tag
class H4(HtmlPhrasing):
  ''

@_tag
class H5(HtmlPhrasing):
  ''

@_tag
class H6(HtmlPhrasing):
  ''


@_tag
class Head(HtmlNode):
  ''''
  If the document is an iframe srcdoc document or if title information is available from a higher-level protocol:
  Zero or more elements of metadata content, of which no more than one is a title element and no more than one is a base element.
  '''

  @property
  def title(self) -> 'Title': return self._single(Title)


@_tag
class Header(HtmlFlow):
  'Flow content, but with no header or footer element descendants.'

@_tag
class Hgroup(HtmlNode):
  'One or more h1, h2, h3, h4, h5, h6 elements, optionally intermixed with script-supporting elements.'

@_tag
class Hr(HtmlNode):
  'Nothing.'


@_tag
class Html(HtmlNode):
  'A head element followed by a body element.'

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
class I(HtmlPhrasing):
  ''

@_tag
class Img(HtmlNode):
  'Nothing.'

@_tag
class Input(HtmlNode):
  ''

@_tag
class Ins(HtmlTransparent):
  ''

@_tag
class Kbd(HtmlPhrasing):
  ''

@_tag
class Label(HtmlPhrasing):
  '''
  Phrasing content, but with no descendant labelable elements unless it is the element's labeled control,
  and no descendant label elements.
  '''

@_tag
class Li(HtmlFlow):
  ''

@_tag
class Link(HtmlNode):
  ''

@_tag
class Main(HtmlFlow):
  ''

@_tag
class Map(HtmlNode):
  ''

@_tag
class Mark(HtmlPhrasing):
  ''

@_tag
class Math(HtmlNode):
  ''

@_tag
class Menu(HtmlNode):
  'Zero or more li and script-supporting elements.'

@_tag
class Meta(HtmlNode):
  ''

@_tag
class Meter(HtmlNode):
  ''

@_tag
class Nav(HtmlFlow):
  ''

@_tag
class Noscript(HtmlNode):
  '''
  When scripting is disabled, in a head element:
  in any order, zero or more link elements, zero or more style elements, and zero or more meta elements.
  '''

@_tag
class Object(HtmlNode):
  ''

@_tag
class Ol(HtmlNode):
  'Zero or more li and script-supporting elements.'

@_tag
class Output(HtmlNode):
  ''

@_tag
class P(HtmlPhrasing):
  ''

@_tag
class Picture(HtmlNode):
  'Zero or more source elements, followed by one img element, optionally intermixed with script-supporting elements.'

@_tag
class Pre(HtmlPhrasing):
  ''

@_tag
class Progress(HtmlNode):
  ''

@_tag
class Q(HtmlPhrasing):
  ''

@_tag
class Rp(HtmlNode):
  'Content model: text.'

@_tag
class Rt(HtmlPhrasing):
  ''

@_tag
class Ruby(HtmlNode):
  ''

@_tag
class S(HtmlPhrasing):
  ''

@_tag
class Samp(HtmlPhrasing):
  ''

@_tag
class Script(HtmlNode):
  ''

@_tag
class Section(HtmlFlow):
  ''

@_tag
class Select(HtmlNode):
  ''

@_tag
class Slot(HtmlTransparent):
  ''

@_tag
class Small(HtmlPhrasing):
  ''

@_tag
class Source(HtmlNode):
  'Content model: nothing.'

@_tag
class Span(HtmlPhrasing):
  ''

@_tag
class Strong(HtmlPhrasing):
  ''

@_tag
class Style(HtmlNode):
  ''

@_tag
class Sub(HtmlPhrasing):
  ''

@_tag
class Summary(HtmlPhrasing):
  ''

@_tag
class Sup(HtmlPhrasing):
  ''

@_tag
class Svg(HtmlNode):
  ''

@_tag
class Table(HtmlNode):
  '''
  In this order: optionally a caption element, followed by zero or more colgroup elements, followed optionally by a thead element,
  followed by either zero or more tbody elements or one or more tr elements, followed optionally by a tfoot element,
  optionally intermixed with one or more script-supporting elements.
  '''

@_tag
class Tbody(HtmlNode):
  'Zero or more tr and script-supporting elements.'

@_tag
class Td(HtmlFlow):
  ''

@_tag
class Template(HtmlNode):
  ''

@_tag
class Text(HtmlNode):
  ''

@_tag
class Textarea(HtmlNode):
  ''

@_tag
class Tfoot(HtmlNode):
  'Zero or more tr and script-supporting elements.'

@_tag
class Th(HtmlNode):
  'Flow content, but with no header, footer, sectioning content, or heading content descendants.'

@_tag
class Thead(HtmlNode):
  'Zero or more tr and script-supporting elements.'

@_tag
class Time(HtmlPhrasing):
  'If the element has a datetime attribute: Phrasing content.'

@_tag
class Title(HtmlNode):
  'Content model: Text that is not inter-element whitespace.'

@_tag
class Tr(HtmlNode):
  'Zero or more td, th, and script-supporting elements.'

@_tag
class U(HtmlPhrasing):
  ''

@_tag
class Ul(HtmlNode):
  'Zero or more li and script-supporting elements.'

@_tag
class Var(HtmlPhrasing):
  ''

@_tag
class Video(HtmlNode):
  ''

@_tag
class Wbr(HtmlNode):
  ''
