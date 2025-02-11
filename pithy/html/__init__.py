# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Html type hierarchy.
'''

import re
from html import escape as _escape
from io import BytesIO, StringIO
from os import PathLike
from typing import Any, BinaryIO, Callable, ClassVar, Iterable, Iterator, Mapping, NoReturn, Self, TextIO, Union

from ..default import Default
from ..exceptions import ConflictingValues, DeleteNode, FlattenNode, MultipleMatchesError, NoMatchError
from ..markup import _Mu, _MuChild, Mu, MuAttrs, MuChild, MuChildLax, MuChildOrChildrenLax, Present, single_child_property
from ..svg import Svg
from . import semantics


_convenience_exports = (ConflictingValues, DeleteNode, FlattenNode, MultipleMatchesError, NoMatchError, MuChild)


_LxmlFilePath = str | bytes | PathLike[str] | PathLike[bytes]
_LxmlFileReadSource = _LxmlFilePath | BinaryIO | TextIO

DtDdPair = tuple[list['Dt'],list['Dd']]

class HtmlNode(Mu):
  'Abstract HTML node; root class of the hierarchy. For the HTML tag, use `Html`.'

  tag_types:ClassVar[dict[str,type[Mu]]] = { # Dispatch table mapping tag names to Mu subtypes.
    'svg': Svg
  }

  replaced_attrs = {
    'async_' : 'async',
  }

  inline_tags = semantics.phrasing_tags
  void_tags = semantics.void_tags
  ws_sensitive_tags = semantics.ws_sensitive_tags


  @classmethod
  def parse_file(cls, file:_LxmlFileReadSource,  **kwargs:Any) -> 'Html':
    from lxml import etree
    if 'treebuilder' in kwargs: raise ValueError('HtmlNode.parse() requires default `lxml` treebuilder option.')
    parser = etree.HTMLParser(**kwargs)
    tree = etree.parse(file, parser)
    root = tree.getroot()
    if root is None: # Empty or whitespace strings produce None.
      return Html(Body()) # type: ignore[unreachable]
    html = HtmlNode.from_etree(root) # type: ignore[arg-type]
    assert isinstance(html, Html), html
    return html


  @classmethod
  def parse(cls, source:bytes|str, **kwargs:Any) -> 'Html':
    if isinstance(source, bytes):
      kwargs['transport_encoding'] = 'utf-8'
      f:BytesIO|StringIO = BytesIO(source)
    else:
      f = StringIO(source)
    return cls.parse_file(f, **kwargs)


  @property
  def is_phrasing(self) -> bool:
    'Wether or not the node is phrasing content.'
    return False


  @property
  def attr_urls(self) -> Iterator[str]:
   return self.iter_visit(pre=_attr_urls_visit)


  def get_value(self) -> Any:
    '''
    The default implementation of `get_value` simply gets the attribute stored under 'value.'
    This is overridden for Select elements, which return the value of the selected option.
    '''
    return self.get('value')


  def set_value(self, value:Any) -> None:
    '''
    The default implementation of `set_value` simply sets the attribute stored under 'value.'
    This is overridden for Select elements, which set the value of the selected option.
    '''
    self['value'] = value


HtmlNode.generic_tag_type = HtmlNode # Note: this creates a circular reference.


def _attr_urls_visit(node:HtmlNode) -> Iterator[str]:
  for k, v in node.attrs.items():
    if k in attr_keys_for_url_vals:
      if k == 'srcset':
        for el in v.split(','):
          src, _space, _descriptor = el.partition(' ')
          yield src
      else:
        yield v


attr_keys_for_url_vals = frozenset({
  'action', # Form URI.
  'cite',
  'data', # Object.
  'formaction',
  'href',
  'poster',
  'src',
  'srcset',
})


def html_id_for(title:str) -> str:
  '''
  HTML4 IDs consist of ASCII letters, digits, '_', '-' and '.'
  HTML5 no longer has this restriction.
  We choose to restrict IDs to Unicode letters, digits, '_', '-' and '.'
  '''
  return html_id_invalid_re.sub('_', title)

html_id_invalid_re = re.compile(r'[^-.\w]+')


def _tag(Subclass:type[_Mu]) -> type[_Mu]:
  'Decorator for associating a concrete subclass with the lowercase tag matching its name.'
  assert issubclass(Subclass, Mu)
  Subclass.tag = Subclass.__name__.lower()
  HtmlNode.tag_types[Subclass.tag] = Subclass
  return Subclass


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
  The superclass of H1-H6 heading elements themselves is `Heading`.
  '''

  def h1(self, attrs:MuAttrs|None=None, _:MuChildOrChildrenLax=(), cl:Iterable[str]|None=None, **kw_attrs:Any) -> 'H1':
    return self.append(H1(attrs=attrs, _=_, cl=cl, **kw_attrs))

  def h2(self, attrs:MuAttrs|None=None, _:MuChildOrChildrenLax=(), cl:Iterable[str]|None=None, **kw_attrs:Any) -> 'H2':
    return self.append(H2(attrs=attrs, _=_, cl=cl, **kw_attrs))

  def h3(self, attrs:MuAttrs|None=None, _:MuChildOrChildrenLax=(), cl:Iterable[str]|None=None, **kw_attrs:Any) -> 'H3':
    return self.append(H3(attrs=attrs, _=_, cl=cl, **kw_attrs))

  def h4(self, attrs:MuAttrs|None=None, _:MuChildOrChildrenLax=(), cl:Iterable[str]|None=None, **kw_attrs:Any) -> 'H4':
    return self.append(H4(attrs=attrs, _=_, cl=cl, **kw_attrs))

  def h5(self, attrs:MuAttrs|None=None, _:MuChildOrChildrenLax=(), cl:Iterable[str]|None=None, **kw_attrs:Any) -> 'H5':
    return self.append(H5(attrs=attrs, _=_, cl=cl, **kw_attrs))

  def h6(self, attrs:MuAttrs|None=None, _:MuChildOrChildrenLax=(), cl:Iterable[str]|None=None, **kw_attrs:Any) -> 'H6':
    return self.append(H6(attrs=attrs, _=_, cl=cl, **kw_attrs))

  @property
  def heading(self) -> HtmlNode|None:
    for el in self._:
      if isinstance(el, Heading): return el
    return None


class HtmlMetadataContent(HtmlNode):
  'Metadata content model: all node types that can contain metadata.'
  # TODO: metadata constructor methods.


class HtmlPhrasingContent(HtmlNode):
  '''
  Phrasing content model: all node types that can contain phrasing content.
  '''


  def labeled_checkboxes(self, *, require_one:bool, desc_singular:str='', choices:Iterable[Any]|Mapping[str,Any],
   checked:Iterable[Any]|Mapping[str,Any]=()) -> Self:
    '''
    Add a sequence of checkboxes to the node.
    '''
    if require_one:
      self['once'] = 'setupValidateAtLeastOneCheckbox(this)'
    if desc_singular:
      self['desc-singular'] = desc_singular

    if isinstance(choices, Mapping): choices = choices.items()

    if isinstance(checked, Mapping):
      checked_set = frozenset(k for k, v in checked.items() if v)
    else:
      checked_set = frozenset(checked)

    for c in choices:
      if isinstance(c, tuple):
        name, desc = c
      else:
        name = desc = c
      is_checked = (name in checked_set)
      self.append(Label(
        Input(type='checkbox', name=name, checked=Present(is_checked)),
        desc))
    return self


  def labeled_radios(self, name:str, *, is_opt:bool=False, checked:Any=Default._, choices:Iterable[Any]|Mapping[str,Any]) \
   -> Self:
    '''
    Add a sequence of radio buttons to the node.
    If `is_opt` is False, the radio buttons will have the `required` attribute (set to the empty string).
    If `checked` is provided, the radio button with the corresponding value will be checked.
    If `choices` is a mapping or a sequence of pairs, the keys will be used as the radio button values and the values as the radio button labels.
    If `choices` is a sequence of non-tuple values, the values will be used as both the radio button values and labels.
    '''
    if isinstance(choices, Mapping): choices = choices.items()
    for c in choices:
      if isinstance(c, tuple):
        value, desc = c
      else:
        value = desc = c
      is_checked = (value == checked) and checked != Default._
      self.append(
        Label(Input(type='radio', name=name, value=value, required=Present(not is_opt), checked=Present(is_checked)),
        desc))
    return self



class HtmlScriptSupporting(HtmlNode):

  def script(self, attrs:MuAttrs|None=None, _:MuChildOrChildrenLax=(), cl:Iterable[str]|None=None,**kw_attrs:Any) -> 'Script':
    return self.append(Script(attrs=attrs, _=_, cl=cl, **kw_attrs))


class HtmlTextContent(HtmlNode):
  'All node types that can contain text content.'


class HtmlTransparentContent(HtmlNode):
  'Transparent content elements.'


class HtmlTransparentPhrasing(HtmlTransparentContent):
  'Nodes are considered phrasing content if all of their children are phrasing content.'
  @property
  def is_phrasing(self) -> bool:
    return all((not isinstance(c, Html) or c.is_phrasing) for c in self._)


class HtmlFlowContent(HtmlHeadingContent, HtmlPhrasingContent):
  '''
  All elements that can contain flow content.
  '''
  # TODO: flow constructor methods.


# Elements.


@_tag
class A(HtmlFlow, HtmlInteractive, HtmlPalpable, HtmlPhrasing, HtmlTransparentContent):
  '''
  Creates a hyperlink to other web pages, files, locations within the same page, email addresses, or any other URL.

  Categories:
    Interactive: if the element has an href attribute.

  Content model:
    Transparent: there must be no interactive content or a element descendants.

  Contexts for use: Phrasing.
  '''

  @classmethod
  def maybe(cls, text:str, transform:Callable[[str],str]|None=None) -> Union['A',str]:
    '''
    Create a link element if the text looks like it starts with a URL. Otherwise, return the plain text as-is.
    If the URL does not appear to span the entire text, create a link element with the entire text as its content.
    Note: the parsing rule is that whitespace, possibly preceded by the characters  `.,;:`, terminates a URL.
    See also pithy.html.parse.linkify.
    '''
    if text.startswith('http://') or text.startswith('https://'):
      if m := re.search(r'[.,;:]?\s', text):
        url_end = m.start()
      else:
        url_end = len(text)
      return cls(href=text[:url_end], _=(transform(text) if transform else text))
    return text


@_tag
class Abbr(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''
  Represents an abbreviation or acronym; the optional title attribute can provide an expansion or description for the abbreviation.

  Contexts for use: Phrasing.
  '''


@_tag
class Address(HtmlFlow, HtmlPalpable, HtmlFlowContent):
  '''
  Indicates that the enclosed HTML provides contact information for a person or people, or for an organization.

  Content model:
    Flow: with no heading content descendants, no sectioning content descendants, and no header, footer, or address element descendants.

  Contexts for use: Flow.
  '''


@_tag
class Area(HtmlFlow, HtmlPhrasing, HtmlNoContent):
  '''
  Defines a hot-spot region on an image, and optionally associates it with a hypertext link. This is used only within a <map> element.

  Contexts for use: Where phrasing content is expected, but only if there is a map element ancestor.
  '''


@_tag
class Article(HtmlFlow, HtmlPalpable, HtmlSectioning, HtmlFlowContent):
  '''
  Represents a self-contained composition in a document, page, application, or site, which is intended to be independently distributable or reusable.

  Contexts for use: Flow.
  '''


@_tag
class Aside(HtmlFlow, HtmlPalpable, HtmlSectioning, HtmlFlowContent):
  '''
  Represents a portion of a document whose content is only indirectly related to the document's main content.

  Contexts for use: Flow.
  '''


@_tag
class Audio(HtmlEmbedded, HtmlFlow, HtmlInteractive, HtmlPalpable, HtmlPhrasing):
  '''
  Used to embed sound content in documents. It may contain one or more audio sources, represented using the src attribute or the <source> element: the browser will choose the most suitable one. It can also be the destination for streamed media, using a MediaStream.

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
  Used to draw the reader's attention to the element's contents, which are not otherwise granted special importance.

  Contexts for use: Phrasing.
  '''


@_tag
class Base(HtmlMetadata, HtmlNoContent):
  '''
  Specifies the base URL to use for all relative URLs contained within a document. There can be only one <base> element in a document.

  Contexts for use: In a head element containing no other base elements.
  '''


@_tag
class Bdi(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''
  Tells the browser's bidirectional algorithm to treat the text it contains in isolation from its surrounding text.

  Contexts for use: Phrasing.
  '''


@_tag
class Bdo(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''
  Overrides the current directionality of text, so that the text within is rendered in a different direction.

  Contexts for use: Phrasing.
  '''


@_tag
class Blockquote(HtmlFlow, HtmlPalpable, HtmlSectioningRoot, HtmlFlowContent):
  '''
  Indicates that the enclosed text is an extended quotation. Usually, this is rendered visually by indentation (see Notes for how to change it). A URL for the source of the quotation may be given using the cite attribute, while a text representation of the source can be given using the <cite> element.

  Contexts for use: Flow.
  '''


@_tag
class Body(HtmlSectioningRoot, HtmlFlowContent):
  '''
  Represents the content of an HTML document. There can be only one <body> element in a document.

  Contexts for use: As the second element in an html element.
  '''

  @single_child_property
  def header(self) -> 'Header': return Header()

  @single_child_property
  def nav(self) -> 'Nav': return Nav()


  @single_child_property
  def main(self) -> 'Main': return Main()


  @single_child_property
  def footer(self) -> 'Footer': return Footer()


@_tag
class Br(HtmlFlow, HtmlPhrasing, HtmlNoContent):
  '''
  Produces a line break in text (carriage-return). It is useful for writing a poem or an address, where the division of lines is significant.

  Contexts for use: Phrasing.
  '''

  @property
  def texts(self) -> Iterator[str]:
    yield from super().texts
    yield '\n'


@_tag
class Button(HtmlFlow, HtmlInteractive, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''
  Represents a clickable button, which can be used in forms or anywhere in a document that needs simple, standard button functionality.

  Categories:
    Listed, labelable, submittable, and autocapitalize-inheriting form-associated element: None.

  Content model:
    Phrasing: there must be no interactive content descendant.

  Contexts for use: Phrasing.
  '''


@_tag
class Canvas(HtmlEmbedded, HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlTransparentContent):
  '''
  Used with either the canvas scripting API or the WebGL API to draw graphics and animations.

  Content model:
    Transparent: with no interactive content descendants except for a elements, img elements with usemap attributes, button elements, input elements whose type attribute are in the Checkbox or Radio Button states, input elements that are buttons, select elements with a multiple attribute or a display size greater than 1, and elements that would not be interactive content except for having the tabindex attribute specified.

  Contexts for use: Embedded.
  '''


@_tag
class Caption(HtmlFlowContent):
  '''
  Specifies the caption (or title) of a table, and if used is always the first child of a <table>.

  Content model:
    Flow: with no descendant table elements.

  Contexts for use: As the first element child of a table element.
  '''


@_tag
class Cite(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''
  Used to describe a reference to a cited creative work, and must include the title of that work.

  Contexts for use: Phrasing.
  '''


@_tag
class Code(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''
  Displays its contents styled in a fashion intended to indicate that the text is a short fragment of computer code.

  Contexts for use: Phrasing.
  '''


@_tag
class Col(HtmlNoContent):
  '''
  Defines a column within a table and is used for defining common semantics on all common cells. It is generally found within a <colgroup> element.

  Contexts for use: As a child of a colgroup element that does not have a span attribute.
  '''


@_tag
class Colgroup(HtmlNode):
  '''
  Defines a group of columns within a table.

  Content model:
    No: if the span attribute is present.
    Zero or more col and template elements: if the span attribute is absent.

  Contexts for use: As a child of a table element, after any caption elements and before any thead, tbody, tfoot, and tr elements.
  '''


@_tag
class Data(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''
  Links a given content with a machine-readable translation. If the content is time- or date-related, the <time> element must be used.

  Contexts for use: Phrasing.
  '''


@_tag
class Datalist(HtmlFlow, HtmlPhrasing):
  '''
  Contains a set of <option> elements that represent the values available for other controls.

  Content model:
    Either: phrasing: None.
    Or: Zero or more option and script-supporting elements: None.

  Contexts for use: Phrasing.
  '''


@_tag
class Dd(HtmlFlowContent):
  '''
  Provides the details about or the definition of the preceding term (<dt>) in a description list (<dl>).

  Contexts for use: After dt or dd elements inside div elements that are children of a dl element, After dt or dd elements inside dl elements.
  '''


@_tag
class Del(HtmlFlow, HtmlPhrasing, HtmlTransparentContent):
  '''
  Represents a range of text that has been deleted from a document.

  Contexts for use: Phrasing.
  '''


@_tag
class Details(HtmlFlow, HtmlInteractive, HtmlPalpable, HtmlSectioningRoot):
  '''
  Creates a disclosure widget in which information is visible only when the widget is toggled into an "open" state.

  Content model:
    One summary element followed by flow: None.

  Contexts for use: Flow.
  '''
  # TODO: summary property.


@_tag
class Dfn(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''
  Used to indicate the term being defined within the context of a definition phrase or sentence.

  Content model:
    Phrasing: there must be no dfn element descendants.

  Contexts for use: Phrasing.
  '''

  def dfn(self) -> NoReturn: raise TypeError('`dfn` elements cannot have `dfn` descendants.')


@_tag
class Dialog(HtmlFlow, HtmlSectioningRoot, HtmlFlowContent):
  '''
  Represents a dialog box or other interactive component, such as an inspector or window.

  Contexts for use: Flow.
  '''


@_tag
class Div(HtmlFlow, HtmlPalpable, HtmlFlowContent):
  '''
  The generic container for flow content. It has no effect on the content or layout until styled using CSS.

  Content model:
    Flow: if the element is not a child of a dl element.
    One or more dt elements followed by one or more dd elements, optionally intermixed with script-supporting elements: if the element is a child of a dl element.

  Contexts for use: As a child of a dl element, Flow.
  '''


@_tag
class Dl(HtmlFlow, HtmlPalpable):
  '''
  Represents a description list. The element encloses a list of groups of terms (specified using the <dt> element) and descriptions (provided by <dd> elements). Common uses for this element are to implement a glossary or to display metadata (a list of key-value pairs).

  Categories:
    Palpable: if the element's children include at least one name-value group.

  Content model:
    Either: Zero or more groups each consisting of one or more dt elements followed by one or more dd elements, optionally intermixed with script-supporting elements: None.
    Or: One or more div elements, optionally intermixed with script-supporting elements: None.

  Contexts for use: Flow.
  '''

  @property
  def dt_dd_groups(self) -> Iterable[Div|DtDdPair]:
    pair:DtDdPair|None = None
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
  Specifies a term in a description list, and as such must be used inside a <dl> element.

  Content model:
    Flow: with no header, footer, sectioning content, or heading content descendants.

  Contexts for use: Before dd or dt elements inside div elements that are children of a dl element, Before dd or dt elements inside dl elements.
  '''


@_tag
class Em(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''
  Marks text that has stress emphasis. The <em> element can be nested, with each level of nesting indicating a greater degree of emphasis.

  Contexts for use: Phrasing.
  '''


@_tag
class Embed(HtmlEmbedded, HtmlFlow, HtmlInteractive, HtmlPalpable, HtmlPhrasing, HtmlNoContent):
  '''
  Embeds external content at the specified point in the document. This content is provided by an external application or other source of interactive content such as a browser plug-in.

  Contexts for use: Embedded.
  '''


@_tag
class Fieldset(HtmlFlow, HtmlPalpable, HtmlSectioningRoot):
  '''
  Used to group several controls as well as labels (<label>) within a web form.

  Categories:
    Listed and autocapitalize-inheriting form-associated element: None.

  Content model:
    Optionally a legend element, followed by flow: None.

  Contexts for use: Flow.
  '''


@_tag
class Figcaption(HtmlFlowContent):
  '''
  Represents a caption or legend describing the rest of the contents of its parent <figure> element.

  Contexts for use: As the first or last child of a figure element.
  '''


@_tag
class Figure(HtmlFlow, HtmlPalpable, HtmlSectioningRoot):
  '''
  Represents self-contained content, potentially with an optional caption, which is specified using the (<figcaption>) element.

  Content model:
    Either: one figcaption element followed by flow: None.
    Or: flow: None.
    Or: flow content followed by one figcaption element: None.

  Contexts for use: Flow.
  '''


@_tag
class Footer(HtmlFlow, HtmlPalpable, HtmlFlowContent):
  '''
  Represents a footer for its nearest sectioning content or sectioning root element. A footer typically contains information about the author of the section, copyright data or links to related documents.

  Content model:
    Flow: with no header or footer element descendants.

  Contexts for use: Flow.
  '''


@_tag
class Form(HtmlFlow, HtmlPalpable, HtmlFlowContent):
  '''
  Represents a document section that contains interactive controls for submitting information to a web server.

  Content model:
    Flow: with no form element descendants.

  Contexts for use: Flow.
  '''


class Heading(HtmlPhrasingContent):
  '''
  Parent class for H1-H6 heading elements, which represent six levels of section headings. <h1> is the highest section level and <h6> is the lowest.

  Contexts for use: As a child of an hgroup element, Flow.
  '''

  @classmethod
  def for_level(cls, level:int, *, attrs:MuAttrs|None=None, _:MuChildOrChildrenLax=(), cl:Iterable[str]|None=None, **kw_attrs:Any) -> 'Heading':
    c = _heading_classes[min(level, 6) - 1]
    return c(attrs=attrs, _=_, cl=cl, **kw_attrs)


@_tag
class H1(Heading):
  'H1 heading.'

@_tag
class H2(Heading):
  'H2 heading.'

@_tag
class H3(Heading):
  'H3 heading.'

@_tag
class H4(Heading):
  'H4 heding.'

@_tag
class H5(Heading):
  'H5 heading.'

@_tag
class H6(Heading):
  'H6 heading.'

_heading_classes:list[type[Heading]] = [H1, H2, H3, H4, H5, H6]


@_tag
class Head(HtmlMetadataContent):
  '''
  Contains machine-readable information (metadata) about the document, like its title, scripts, and style sheets.

  Content model:
    Zero or more elements of metadata content, of which no more than one is a title element and no more than one is a base element: if the document is an iframe srcdoc document or if title information is available from a higher-level protocol.
    One or more elements of metadata content, of which exactly one is a title element and no more than one is a base element: Otherwise.

  Contexts for use: As the first element in an html element.
  '''

  @single_child_property
  def style(self) -> 'Style': return Style()

  @single_child_property
  def title(self) -> 'Title': return Title()

  def add_stylesheet(self, url:str, media='all') -> None:
    self.append(Link(rel='stylesheet', media=media, href=url))

  def add_js(self, *, url:str, defer=True, async_=False) -> None:
    self.append(Script(type='text/javascript', src=url, defer=Present(defer), async_=Present(async_)))


@_tag
class Header(HtmlFlow, HtmlPalpable, HtmlFlowContent):
  '''
  Represents introductory content, typically a group of introductory or navigational aids. It may contain some heading elements but also a logo, a search form, an author name, and other elements.

  Content model:
    Flow: with no header or footer element descendants.

  Contexts for use: Flow.
  '''


@_tag
class Hgroup(HtmlFlow, HtmlHeading, HtmlPalpable):
  '''
  Represents a multi-level heading for a section of a document. It groups a set of <h1>–<h6> elements.

  Content model:
    One or more h1, h2, h3, h4, h5, h6 elements, optionally intermixed with script-supporting elements: None.

  Contexts for use: Flow.
  '''


@_tag
class Hr(HtmlFlow, HtmlNoContent):
  '''
  Represents a thematic break between paragraph-level elements: for example, a change of scene in a story, or a shift of topic within a section.

  Contexts for use: Flow.
  '''


@_tag
class Html(HtmlNode):
  '''
  Represents the root (top-level element) of an HTML document, so it is also referred to as the root element. All other elements must be descendants of this element.

  Content model:
    A head element followed by a body element: None.

  Contexts for use: As document's document element, Wherever a subdocument fragment is allowed in a compound document.
  '''

  def render(self, newline:bool=True) -> Iterator[str]:
    yield '<!DOCTYPE html>\n'
    yield from super().render(newline=newline)

  @single_child_property
  def body(self) -> Body: return Body()

  @single_child_property
  def head(self) -> Head: return Head()

  @staticmethod
  def doc(*, lang='en', charset='utf-8', title:str='') -> 'Html':
    html = Html(lang=lang)
    head = html.head
    head.append(Meta(charset=charset))
    if title:
      head.title.append(title)
    return html


@_tag
class I(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''
  Represents a range of text that is set off from the normal text for some reason. Some examples include technical terms, foreign language phrases, or fictional character thoughts. It is typically displayed in italic type.

  Contexts for use: Phrasing.
  '''


@_tag
class Iframe(HtmlEmbedded, HtmlFlow, HtmlInteractive, HtmlPalpable, HtmlPhrasing, HtmlNoContent):
  '''
  Represents a nested browsing context, embedding another HTML page into the current one.

  Contexts for use: Embedded.
  '''


@_tag
class Img(HtmlEmbedded, HtmlFlow, HtmlInteractive, HtmlPalpable, HtmlPhrasing, HtmlNoContent):
  '''
  Embeds an image into the document. It is a replaced element.

  Categories:
    Form-associated element: None.
    Interactive: if the element has a usemap attribute.

  Contexts for use: Embedded.
  '''


@_tag
class Input(HtmlFlow, HtmlInteractive, HtmlPalpable, HtmlPhrasing, HtmlNoContent):
  '''
  Used to create interactive controls for web-based forms in order to accept data from the user; a wide variety of types of input data and control widgets are available, depending on the device and user agent.

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
  Represents a range of text that has been added to a document.

  Contexts for use: Phrasing.
  '''


@_tag
class Kbd(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''
  Represents a span of inline text denoting textual user input from a keyboard, voice input, or any other text entry device.

  Contexts for use: Phrasing.
  '''


@_tag
class Label(HtmlFlow, HtmlInteractive, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''
  Represents a caption for an item in a user interface.

  Content model:
    Phrasing: with no descendant labelable elements unless it is the element's labeled control, and no descendant label elements.

  Contexts for use: Phrasing.
  '''


@_tag
class Legend(HtmlPhrasingContent):
  '''
  Represents a caption for the content of its parent <fieldset>.

  Contexts for use: As the first child of a fieldset element.
  '''


@_tag
class Li(HtmlFlowContent):
  '''
  Used to represent an item in a list.

  Contexts for use: Inside menu elements, Inside ol elements, Inside ul elements.
  '''


@_tag
class Link(HtmlFlow, HtmlMetadata, HtmlPhrasing, HtmlNoContent):
  '''
  The HTML External Resource Link element (<link>) specifies relationships between the current document and an external resource. This element is most commonly used to link to stylesheets, but is also used to establish site icons (both "favicon" style icons and icons for the home screen and apps on mobile devices) among other things.

  Categories:
    Flow: if the element is allowed in the body.
    Phrasing: if the element is allowed in the body.

  Contexts for use: If the element is allowed in the body: where phrasing content is expected, In a noscript element that is a child of a head element, Where metadata content is expected.
  '''


@_tag
class Main(HtmlFlow, HtmlPalpable, HtmlFlowContent):
  '''
  Represents the dominant content of the <body> of a document. The main content area consists of content that is directly related to or expands upon the central topic of a document, or the central functionality of an application.

  Contexts for use: Where flow content is expected, but only if it is a hierarchically correct main element.
  '''


@_tag
class Map(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlTransparentContent):
  '''
  Used with <area> elements to define an image map (a clickable link area).

  Contexts for use: Phrasing.
  '''


@_tag
class Mark(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''
  Represents text which is marked or highlighted for reference or notation purposes, due to the marked passage's relevance or importance in the enclosing context.

  Contexts for use: Phrasing.
  '''


@_tag
class Math(HtmlNode):
  '''
  Represents a mathematical expression.

  Contexts for use: Phrasing.
  '''


@_tag
class Menu(HtmlFlow, HtmlPalpable):
  '''
  Represents a group of commands that a user can perform or activate. This includes both list menus, which might appear across the top of a screen, as well as context menus, such as those that might appear underneath a button after it has been clicked.

  Categories:
    Palpable: if the element's children include at least one li element.

  Content model:
    Zero or more li and script-supporting elements: None.

  Contexts for use: Flow.
  '''


@_tag
class Meta(HtmlFlow, HtmlMetadata, HtmlPhrasing, HtmlNoContent):
  '''
  Represents metadata that cannot be represented by other HTML meta-related elements, like <base>, <link>, <script>, <style> or <title>.

  Categories:
    Flow: if the itemprop attribute is present.
    Phrasing: if the itemprop attribute is present.

  Contexts for use: If the charset attribute is present, or if the element's http-equiv attribute is in the Encoding declaration state: in a head element, If the http-equiv attribute is present but not in the Encoding declaration state: in a head element, If the http-equiv attribute is present but not in the Encoding declaration state: in a noscript element that is a child of a head element, If the itemprop attribute is present: where metadata content is expected, If the itemprop attribute is present: where phrasing content is expected, If the name attribute is present: where metadata content is expected.
  '''


@_tag
class Meter(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''
  Represents either a scalar value within a known range or a fractional value.

  Categories:
    Labelable element: None.

  Content model:
    Phrasing: there must be no meter element descendants.

  Contexts for use: Phrasing.
  '''


@_tag
class Nav(HtmlFlow, HtmlPalpable, HtmlSectioning, HtmlFlowContent):
  '''
  Represents a section of a page whose purpose is to provide navigation links, either within the current document or to other documents. Common examples of navigation sections are menus, tables of contents, and indexes.

  Contexts for use: Flow.
  '''


@_tag
class Noscript(HtmlFlow, HtmlMetadata, HtmlPhrasing):
  '''
  Defines a section of HTML to be inserted if a script type on the page is unsupported or if scripting is currently turned off in the browser.

  Content model:
    Otherwise: text that conforms to the requirements given in the prose: None.
    When scripting is disabled, in a head element: in any order, zero or more link elements, zero or more style elements, and zero or more meta elements: None.
    When scripting is disabled, not in a head element: transparent: there must be no noscript element descendants.

  Contexts for use: In a head element of an HTML document, if there are no ancestor noscript elements, Where phrasing content is expected in HTML documents, if there are no ancestor noscript elements.
  '''


@_tag
class Object(HtmlEmbedded, HtmlFlow, HtmlInteractive, HtmlPalpable, HtmlPhrasing):
  '''
  Represents an external resource, which can be treated as an image, a nested browsing context, or a resource to be handled by a plugin.

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
  Represents an ordered list of items, typically rendered as a numbered list.

  Categories:
    Palpable: if the element's children include at least one li element.

  Content model:
    Zero or more li and script-supporting elements: None.

  Contexts for use: Flow.
  '''


@_tag
class Optgroup(HtmlNode):
  '''
  Creates a grouping of options within a <select> element.

  Content model:
    Zero or more option and script-supporting elements: None.

  Contexts for use: As a child of a select element.
  '''

  def __call__(self, *options:Any) -> Self:
    '''
    Call an instance to configure it with options.
    '''
    for o in options:
      if isinstance(o, Option):
        self.append(o)
      elif isinstance(o, tuple):
        if len(o) != 2: raise ValueError(f'Optgroup tuple option must be a pair; received: {o}')
        v = str(o[0])
        self.append(Option(value=v, _=str(o[1])))
      else:
        v = str(o)
        self.append(Option(value=v, _=v))
    return self


@_tag
class Option(HtmlTextContent):
  '''
  Used to define an item contained in a <select>, an <optgroup>, or a <datalist> element. As such, <option> can represent menu items in popups and other lists of items in an HTML document.

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
  Used to inject the results of a calculation or the outcome of a user action.

  Categories:
    Listed, labelable, resettable, and autocapitalize-inheriting form-associated element: None.

  Contexts for use: Phrasing.
  '''


@_tag
class P(HtmlFlow, HtmlPalpable, HtmlPhrasingContent):
  '''
  Represents a paragraph.

  Contexts for use: Flow.
  '''

  @property
  def texts(self) -> Iterator[str]:
    yield from super().texts
    yield '\n\n'


@_tag
class Param(HtmlNoContent):
  '''
  Defines parameters for an <object> element.

  Contexts for use: As a child of an object element, before any flow content.
  '''


@_tag
class Picture(HtmlEmbedded, HtmlFlow, HtmlPhrasing):
  '''
  Contains zero or more <source> elements and one <img> element to provide versions of an image for different display/device scenarios.

  Content model:
    Zero or more source elements, followed by one img element, optionally intermixed with script-supporting elements: None.

  Contexts for use: Embedded.
  '''


@_tag
class Pre(HtmlFlow, HtmlPalpable, HtmlPhrasingContent):
  '''
  Represents preformatted text which is to be presented exactly as written in the HTML file.

  Contexts for use: Flow.
  '''


@_tag
class Progress(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''
  Displays an indicator showing the completion progress of a task, typically displayed as a progress bar.

  Categories:
    Labelable element: None.

  Content model:
    Phrasing: there must be no progress element descendants.

  Contexts for use: Phrasing.
  '''


@_tag
class Q(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''
  Indicates that the enclosed text is a short inline quotation. Most modern browsers implement this by surrounding the text in quotation marks.

  Contexts for use: Phrasing.
  '''


@_tag
class Rb(HtmlTextContent):
  '''
  Used to delimit the base text component of a <ruby> annotation, i.e. the text that is being annotated.

  Contexts for use: As a child of a ruby element.
  '''


@_tag
class Rp(HtmlTextContent):
  '''
  Used to provide fall-back parentheses for browsers that do not support display of ruby annotations using the <ruby> element.

  Contexts for use: As a child of a ruby element, either immediately before or immediately after an rt element.
  '''


@_tag
class Rt(HtmlPhrasingContent):
  '''
  Specifies the ruby text component of a ruby annotation, which is used to provide pronunciation, translation, or transliteration information for East Asian typography. The <rt> element must always be contained within a <ruby> element.

  Contexts for use: As a child of a ruby element.
  '''


@_tag
class Rtc(HtmlPhrasingContent):
  '''
  Embraces semantic annotations of characters presented in a ruby of <rb> elements used inside of <ruby> element. <rb> elements can have both pronunciation (<rt>) and semantic (<rtc>) annotations.

  Contexts for use: As a child of a ruby element.
  '''


@_tag
class Ruby(HtmlFlow, HtmlPalpable, HtmlPhrasing):
  '''
  Represents a ruby annotation. Ruby annotations are for showing pronunciation of East Asian characters.

  Content model:
    See prose: None.

  Contexts for use: Phrasing.
  '''


@_tag
class S(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''
  Renders text with a strikethrough, or a line through it. Use the <s> element to represent things that are no longer relevant or no longer accurate. However, <s> is not appropriate when indicating document edits; for that, use the <del> and <ins> elements, as appropriate.

  Contexts for use: Phrasing.
  '''


@_tag
class Samp(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''
  Used to enclose inline text which represents sample (or quoted) output from a computer program.

  Contexts for use: Phrasing.
  '''


@_tag
class Script(HtmlFlow, HtmlMetadata, HtmlPhrasing):
  '''
  Used to embed or reference executable code; this is typically used to embed or refer to JavaScript code.

  Categories:
    Script-supporting element: None.

  Content model:
    : if there is a src attribute, the element must be either empty or contain only script documentation that also matches script content restrictions.
    : if there is no src attribute, depends on the value of the type attribute, but must match script content restrictions.

  Contexts for use: Phrasing, Where metadata content is expected, Where script-supporting elements are expected.
  '''


  @classmethod
  def strict(cls, script:str, **attrs:Any) -> 'Script':
    if not (script.startswith('\'use strict\';') or script.startswith('"use strict";')):
      script = "'use strict';\n" + script
    return Script(script, **attrs)


  @classmethod
  def onDomLoaded(cls, script:str, **attrs:Any) -> 'Script':
    '''
    Embed the script in `script` into a callback function that runs when the DOM is loaded.
    The callback function takes a single argument named `event`.
    Strict mode is automatically enabled.
    '''
    script = f"'use strict';\ndocument.addEventListener('DOMContentLoaded', (event) => {{\n{script}\n}});"
    return Script(script, **attrs)


@_tag
class Section(HtmlFlow, HtmlPalpable, HtmlSectioning, HtmlFlowContent):
  '''
  Represents a standalone section which does not have a more specific semantic element to represent it.

  Contexts for use: Flow.
  '''


@_tag
class Select(HtmlFlow, HtmlInteractive, HtmlPalpable, HtmlPhrasing):
  '''
  Represents a control that provides a menu of options

  Categories:
    Listed, labelable, submittable, resettable, and autocapitalize-inheriting form-associated element: None.

  Content model:
    Zero or more option, optgroup, and script-supporting elements: None.

  Contexts for use: Phrasing.
  '''


  def options(self, options:Iterable[Any]|Mapping[str,Any], placeholder=None, value=None) -> Self:
    '''
    Configure the select element with `options`, an optional `placeholder`, and an optional selected `value`.
    '''
    if placeholder is not None:
      pho = self.append(Option(disabled='', value='', _=str(placeholder)))
    else:
      pho = None

    if value is not None:
      value = str(value)

    if isinstance(options, Mapping): options = options.items()

    has_selected = False
    for o in options:
      option:Option|Optgroup
      if isinstance(o, Option):
        v = o['value']
        option = o
      elif isinstance(o, Optgroup):
        v = None
        option = o
        for oo in o:
          if not isinstance(oo, Option): raise ValueError(f'optgroup must contain only Option elements; received: {oo!r}')
          if value is not None and oo['value'] == value:
            oo['selected'] = ''
            has_selected = True
      elif isinstance(o, tuple):
        if len(o) != 2: raise ValueError(f'tuple option must be a pair; received: {o}')
        v = str(o[0])
        option = Option(value=v, _=str(o[1]))
      else:
        v = str(o)
        option = Option(value=v, _=v)
      if v is not None and v == value: # Always excludes an Optgroup.
        option['selected'] = ''
        has_selected = True
      self.append(option)

    if pho is not None and not has_selected:
      pho['selected'] = ''

    return self


  def get_value(self) -> Any:
    '''
    `Select` overrides the default implementation of `get_value` and returns the value of the selected option or `None`.

    Note the documented behavior in https://developer.mozilla.org/en-US/docs/Web/HTML/Element/select:
    > If no value attribute is included, the value defaults to the text contained inside the element.

    We do not attempt to imitate the default behavior, because if we wanted to make it accurate across all form controls
    we would need to also implement the default behavior for the various kinds of `Input`, e.g. return "on" for checkboxes.
    This is possible but requires more careful research, documentation and testing.
    '''
    for o in self:
      if not isinstance(o, Option): continue
      if 'selected' not in o.attrs: continue
      return o.get('value')
    return None


  def set_value(self, value:Any) -> None:
    '''
    `Select` overrides the default implementation of `set_value` and sets the option with the given value as selected.
    '''
    found = False
    for o in self:
      if not isinstance(o, Option): continue
      if o.get('value') == value:
        o['selected'] = ''
        found = True
      else:
        o.attrs.pop('selected', None)
    if not found and value is not None: raise ValueError(f'Option with value {value!r} not found in Select.')


@_tag
class Slot(HtmlFlow, HtmlPhrasing, HtmlTransparentContent):
  '''
  Used as a placeholder inside a web component that you can fill with your own markup, which lets you create separate DOM trees and present them together.

  Contexts for use: Phrasing.
  '''


@_tag
class Small(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''
  Makes the text font size one size smaller (for example, from large to medium, or from small to x-small) down to the browser's minimum font size.  In HTML5, this element is repurposed to represent side-comments and small print, including copyright and legal text, independent of its styled presentation.

  Contexts for use: Phrasing.
  '''


@_tag
class Source(HtmlNoContent):
  '''
  Specifies multiple media resources for the <picture>, the <audio> element, or the <video> element.

  Contexts for use: As a child of a media element, before any flow content or track elements, As a child of a picture element, before the img element.
  '''


@_tag
class Span(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''
  A generic inline container for phrasing content, which does not inherently represent anything. It can be used to group elements for styling purposes (using the class or id attributes), or because they share attribute values, such as lang.

  Contexts for use: Phrasing.
  '''


@_tag
class Strong(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''
  Indicates that its contents have strong importance, seriousness, or urgency. Browsers typically render the contents in bold type.

  Contexts for use: Phrasing.
  '''


@_tag
class Style(HtmlMetadata):
  '''
  Contains style information for a document, or part of a document.

  Content model:
    Text that gives a conformant style sheet: None.

  Contexts for use: In a noscript element that is a child of a head element, Where metadata content is expected.
  '''


@_tag
class Sub(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''
  Specifies inline text which should be displayed as subscript for solely typographical reasons.

  Contexts for use: Phrasing.
  '''


@_tag
class Summary(HtmlPhrasing):
  '''
  Specifies a summary, caption, or legend for a <details> element's disclosure box.

  Content model:
    Either: phrasing: None.
    Or: one element of heading: None.

  Contexts for use: As the first child of a details element.
  '''


@_tag
class Sup(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''
  Specifies inline text which is to be displayed as superscript for solely typographical reasons.

  Contexts for use: Phrasing.
  '''


@_tag
class Table(HtmlFlow, HtmlPalpable):
  '''
  Represents tabular data: information presented in a two-dimensional table comprised of rows and columns of cells containing data.

  Content model:
    In this order: optionally a caption element, followed by zero or more colgroup elements, followed optionally by a thead element, followed by either zero or more tbody elements or one or more tr elements, followed optionally by a tfoot element, optionally intermixed with one or more script-supporting elements: None.

  Contexts for use: Flow.
  '''

  _th_classes: list[str] = [] # Track the classes of the cells in the last row added by `head()`.

  def caption(self, caption:MuChildLax, *els:MuChildLax) -> Self:
    if not isinstance(caption, Caption):
      caption = Caption(caption)
    self.append(caption)
    caption.extend(els)
    return self


  def cols(self, *cols:Col) -> Self:
    self.append(Colgroup(_=cols))
    return self


  def head(self, head:Union['Thead',Iterable[MuChildLax]]) -> Self:
    '''
    The `head` argument can be a fully formed `Thead` or else an iterable of `Td|Th` or content with which `Th` are constructed.
    If `head` is a `Thead` object and another `Thead` child is present, raise ConflictingValues.
    Otherwise use the existing `Thead` or create a new one and add the elements of `head` to it.

    The classes of each cell in the last row added by `head()` are recorded in a private attribute.
    These classes are applied to the corresponding cells in the last row added by `rows()`.
    '''
    thead = self.pick_opt(Thead) # Raise MultipleMatchesError if more than one Thead is present (against the HTML spec).
    if isinstance(head, Thead):
      if thead: raise ConflictingValues(key=Thead, existing=thead, incoming=head)
      self.append(head)
    else:
      if thead is None: thead = self.append(Thead())
      cells = [cell if isinstance(cell, (Td, Th)) else Th(_=cell) for cell in head]
      thead.append(Tr(_=cells))
      del self._th_classes[:]
      for cell in cells:
        cl = cell.get('class')
        colspan = cell.get('colspan', 1)
        for _ in range(colspan):
          self._th_classes.append(cl)
    return self


  def rows(self, rows:Iterable['Tr'|Iterable[MuChildLax]]) -> Self:
    '''
    Create a `Tbody` and add `Tr` elements to it, each of which is constructed from the elements of the corresponding row.
    Elements of `rows` that are not `Tr` elements must be iterables either `Td`, `Th` or content with which `Td` are constructed.
    '''
    tbody = self.append(Tbody())
    for row in rows:
      if isinstance(row, Tr):
        tr = row
      else:
        tr = Tr(_=[cell if isinstance(cell, (Td, Th)) else Td(_=cell) for cell in row])
      tbody.append(tr)
      th_cl_i = 0
      for cell in tr._:
        assert isinstance(cell, (Td, Th))
        colspan = cell.get('colspan', 1)
        try: th_cl = self._th_classes[th_cl_i]
        except IndexError: th_cl = None
        if th_cl:
          if existing_cl := cell.get('class'):
            cell['class'] = f'{th_cl} {existing_cl}'
          else:
            cell['class'] = th_cl
        th_cl_i += colspan
    return self


@_tag
class Tbody(HtmlNode):
  '''
  Encapsulates a set of table rows (<tr> elements), indicating that they comprise the body of the table (<table>).

  Content model:
    Zero or more tr and script-supporting elements: None.

  Contexts for use: As a child of a table element, after any caption, colgroup, and thead elements, but only if there are no tr elements that are children of the table element.
  '''


@_tag
class Td(HtmlSectioningRoot, HtmlFlowContent):
  '''
  Defines a cell of a table that contains data. It participates in the table model.

  Contexts for use: As a child of a tr element.
  '''


@_tag
class Template(HtmlFlow, HtmlMetadata, HtmlPhrasing):
  '''
  Used to hold HTML that is not to be rendered immediately when a page is loaded but may be instantiated subsequently during runtime using JavaScript.

  Categories:
    Script-supporting element: None.

  Content model:
    Nothing (for clarification, see example): None.

  Contexts for use: As a child of a colgroup element that does not have a span attribute, Phrasing, Where metadata content is expected, Where script-supporting elements are expected.
  '''


@_tag
class TextArea(HtmlFlow, HtmlInteractive, HtmlPalpable, HtmlPhrasing, HtmlTextContent):
  '''
  Represents a multi-line plain-text editing control, useful when you want to allow users to enter a sizeable amount of free-form text, for example a comment on a review or feedback form.

  Categories:
    Listed, labelable, submittable, resettable, and autocapitalize-inheriting form-associated element: None.

  Contexts for use: Phrasing.
  '''


@_tag
class Tfoot(HtmlNode):
  '''
  Defines a set of rows summarizing the columns of the table.

  Content model:
    Zero or more tr and script-supporting elements: None.

  Contexts for use: As a child of a table element, after any caption, colgroup, thead, tbody, and tr elements, but only if there are no other tfoot elements that are children of the table element.
  '''


@_tag
class Th(HtmlFlowContent):
  '''
  Defines a cell as header of a group of table cells. The exact nature of this group is defined by the scope and headers attributes.

  Content model:
    Flow: with no header, footer, sectioning content, or heading content descendants.

  Contexts for use: As a child of a tr element.
  '''


@_tag
class Thead(HtmlNode):
  '''
  Defines a set of rows defining the head of the columns of the table.

  Content model:
    Zero or more tr and script-supporting elements: None.

  Contexts for use: As a child of a table element, after any caption, and colgroup elements and before any tbody, tfoot, and tr elements, but only if there are no other thead elements that are children of the table element.
  '''


@_tag
class Time(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''
  Represents a specific period in time.

  Content model:
    Otherwise: Text: must match requirements described in prose below.
    Phrasing: if the element has a datetime attribute.

  Contexts for use: Phrasing.
  '''


@_tag
class Title(HtmlMetadata):
  '''
  Defines the document's title that is shown in a browser's title bar or a page's tab.

  Content model:
    Text that is not inter-element whitespace: None.

  Contexts for use: In a head element containing no other title elements.
  '''


@_tag
class Tr(HtmlNode):
  '''
  Defines a row of cells in a table. The row's cells can then be established using a mix of <td> (data cell) and <th> (header cell) elements.

  Content model:
    Zero or more td, th, and script-supporting elements: None.

  Contexts for use: As a child of a table element, after any caption, colgroup, and thead elements, but only if there are no tbody elements that are children of the table element, As a child of a tbody element, As a child of a tfoot element, As a child of a thead element.
  '''

  def tds(self, *cells:MuChildLax, **kwargs:Any) -> 'Tr':
    '''
    Add Td child elements from the arguments, each of which is either a Td/Th or else becomes the content of a new Td.
    Each child is updated with the given `kwargs`.
    '''
    for c in cells:
      cell = c if isinstance(c, (Td, Th)) else Td(_=c)
      cell.update(**kwargs)
      self.append(cell)
    return self


  def ths(self, *cells:MuChildLax, **kwargs:Any) -> 'Tr':
    '''
    Add Th child elements from the arguments, each of which is either a Td/Th or else becomes the content of a Th.
    Each child is updated with the given `kwargs`.
    '''
    for c in cells:
      cell = c if isinstance(c, (Td, Th)) else Th(_=c)
      cell.update(**kwargs)
      self.append(cell)
    return self


@_tag
class Track(HtmlNoContent):
  '''
  Used as a child of the media elements <audio> and <video>. It lets you specify timed text tracks (or time-based data), for example to automatically handle subtitles. The tracks are formatted in WebVTT format (.vtt files) — Web Video Text Tracks or Timed Text Markup Language (TTML).

  Contexts for use: As a child of a media element, before any flow content.
  '''


@_tag
class U(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''
  Represents a span of inline text which should be rendered in a way that indicates that it has a non-textual annotation.

  Contexts for use: Phrasing.
  '''


@_tag
class Ul(HtmlFlow, HtmlPalpable):
  '''
  Represents an unordered list of items, typically rendered as a bulleted list.

  Categories:
    Palpable: if the element's children include at least one li element.

  Content model:
    Zero or more li and script-supporting elements: None.

  Contexts for use: Flow.
  '''


@_tag
class Var(HtmlFlow, HtmlPalpable, HtmlPhrasing, HtmlPhrasingContent):
  '''
  Represents the name of a variable in a mathematical expression or a programming context.

  Contexts for use: Phrasing.
  '''


@_tag
class Video(HtmlEmbedded, HtmlFlow, HtmlInteractive, HtmlPalpable, HtmlPhrasing):
  '''
  Embeds a media player which supports video playback into the document.

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
  Represents a word break opportunity: a position within text where the browser may optionally break a line, even if its line-breaking rules would not otherwise create a break at that location.

  Contexts for use: Phrasing.
  '''


class Css(Style):
  '''
  Embedded CSS stylesheet.
  This is a convenience subclass of Style that ensures that all child elements are strings.
  Additionally it checks that the strings do not contain unescaped HTML characters,
  rather than blindly escaping them.
  '''

  def render_children(self) -> Iterator[str]:
    'Override render children to treat children as CSS text.'
    for c in self._:
      if not isinstance(c, str):
        raise TypeError(f'Css children must be strings; recieved: {c!r}')
      if m := html_req_escape_chars_re.search(c):
        raise ValueError(f'Css text cannot contain unescaped char: {c!r}; position: {m.start()}.')
      yield c
      if not c.endswith('\n'): yield '\n'


html_req_escape_chars_re = re.compile(r'([<&])')


def cssi(**styles:int|float|str) -> str:
  '''
  CSS inline value. Creates a string for use as an inline style attribute.
  This function automatically translates underscores to dashes in the key name.
  example: `Div(style=cssiv(font_size='1em', color='red'))`.
  '''
  return ';'.join(f'{k.replace("_", "-")}:{v}' for k, v in styles.items())


def html_esc(text: str) -> str:
  # TODO: check for strange characters that html will ignore.
  return _escape(text, quote=False)


def html_esc_attr(text: str) -> str:
  return _escape(text, quote=True)
