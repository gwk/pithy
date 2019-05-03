# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
HTML writer.
'''

from sys import stdout
from html import escape as html_escape
from types import TracebackType
from typing import Any, Dict, List, Optional, Sequence, TextIO, Tuple, Type, TypeVar, Union, Iterable, cast
from ..range import Num, NumRange
from ..xml import EscapedStr, XmlAttrs, XmlWriter, add_opt_attrs, esc_xml_attr, esc_xml_text
from ..svg import *
from .semantics import form_input_types


Dim = Union[int, float, str]
Vec = Tuple[Num, Num]
VecOrNum = Union[Vec, Num]
PathCommand = Tuple

ViewBox = Union[None, Vec, Tuple[Num, Num, Num, Num], Tuple[Vec, Vec]] # TODO: currently unused.


class HtmlWriter(XmlWriter):
  '''
  HtmlWriter is a ContextManager class for generating HTML.

  '''

  can_auto_close_tags = False # Unlike XML, HTML5 dictates that each tag type either be self-closing or not.

  def a(self, *children:Any, **attrs:Any) -> 'A': return self.child(A, *children, attrs=attrs)

  def br(self) -> None: self.leaf('br', attrs=None)

  def div(self, *children:Any, **attrs:Any) -> 'Div': return self.child(Div, *children, attrs=attrs)

  def img(self, *children:Any, **attrs:Any) -> 'Img': return self.child(Img, *children, attrs=attrs)

  def h1(self, *children:Any, **attrs:Any) -> 'H1': return self.child(H1, *children, attrs=attrs)
  def h2(self, *children:Any, **attrs:Any) -> 'H2': return self.child(H2, *children, attrs=attrs)
  def h3(self, *children:Any, **attrs:Any) -> 'H3': return self.child(H3, *children, attrs=attrs)
  def h4(self, *children:Any, **attrs:Any) -> 'H4': return self.child(H4, *children, attrs=attrs)
  def h5(self, *children:Any, **attrs:Any) -> 'H5': return self.child(H5, *children, attrs=attrs)
  def h6(self, *children:Any, **attrs:Any) -> 'H6': return self.child(H6, *children, attrs=attrs)

  def hr(self) -> None: self.leaf('hr', attrs=None)

  def meta(self, **attrs:Any) -> 'Meta': return self.child(Meta, attrs=attrs)

  def p(self, *children:Any, **attrs:Any) -> 'P': return self.child(P, *children, attrs=attrs)

  def pre(self, *children:Any, **attrs:Any) -> 'Pre': return self.child(Pre, *children, attrs=attrs)

  def span(self, *children:Any, **attrs:Any) -> 'Span': return self.child(Span, *children, attrs=attrs)

  def script(self, *children:Any, **attrs:Any) -> Script: return self.child(Script, *children, attrs=attrs)

  def style(self, *children:Any, **attrs:Any) -> Style: return self.child(Style, *children, attrs=attrs)

  def svg(self, *children:Any, **kwargs:Any) -> Svg:
    return self.child(Svg, *children, **kwargs)

  # Forms.

  def form(self, *children:Any, **attrs:Any) -> 'Form': return self.child(Form, *children, attrs=attrs)

  def input(self, **attrs:Any) -> None:
    # TODO: move to Input class.
    if attrs.get('type') not in form_input_types:
      raise Exception(f'bad HTML <input> type: {attrs.get("type")}')
    return self.leaf('input', attrs=attrs)

  def label(self, *children:Any, **attrs:Any) -> 'Label':
    return self.child(Label, *children, attrs=attrs)

  # Tables.

  # TODO: return XmlWriter subclasses that enforce correct permitted parent/child structures.

  def table(self, *children:Any, **attrs:Any) -> 'Table': return self.child(Table, *children, attrs=attrs)

  def caption(self, *children:Any, **attrs:Any) -> 'Caption': return self.child(Caption, *children, attrs=attrs)

  def thead(self, *children:Any, **attrs:Any) -> 'THead': return self.child(THead, *children, attrs=attrs)

  def tfoot(self, *children:Any, **attrs:Any) -> 'TFoot': return self.child(TFoot, *children, attrs=attrs)

  def td(self, *children:Any, **attrs:Any) -> 'TD': return self.child(TD, *children, attrs=attrs)

  def th(self, *children:Any, **attrs:Any) -> 'TH': return self.child(TH, *children, attrs=attrs)

  def tr(self, *children:Any, **attrs:Any) -> 'TR': return self.child(TR, *children, attrs=attrs)

  def title(self, *children:Any, **attrs:Any) -> 'Title': return self.child(Title, *children, attrs=attrs)


class Html(HtmlWriter):
  tag = 'html'

  def __init__(self, attrs:XmlAttrs=None) -> None:
    super().__init__(attrs=attrs)
    self.prefix = '<!DOCTYPE html>'
    self.head = self.child(Head, attrs=attrs)
    self.head.meta(charset='utf-8')
    self.body = self.child(Body, attrs=attrs)


class A(HtmlWriter):
  tag = 'a'

class Body(HtmlWriter):
  tag = 'body'

class Div(HtmlWriter):
  tag = 'div'

class Img(HtmlWriter):
  tag = 'img'
  is_self_closing = True

class Head(HtmlWriter):
  tag = 'head'

class H1(HtmlWriter):
  tag = 'h1'

class H2(HtmlWriter):
  tag='h2'

class H3(HtmlWriter):
  tag = 'h3'

class H4(HtmlWriter):
  tag = 'h4'

class H5(HtmlWriter):
  tag = 'h5'

class H6(HtmlWriter):
  tag = 'h6'

class P(HtmlWriter):
  tag = 'p'

class Pre(HtmlWriter):
  tag = 'pre'

class Form(HtmlWriter):
  tag = 'form'

class Input(HtmlWriter):
  tag = 'input'

class Label(HtmlWriter):
  tag = 'label'

class Meta(HtmlWriter):
  tag = 'meta'
  is_self_closing = True

class Span(HtmlWriter):
  tag = 'span'

class Table(HtmlWriter):
  tag = 'table'

class Caption(HtmlWriter):
  tag = 'caption'

class THead(HtmlWriter):
  tag = 'thead'

class TFoot(HtmlWriter):
  tag = 'tfoot'

class TD(HtmlWriter):
  tag = 'td'

class TH(HtmlWriter):
  tag = 'th'

class TR(HtmlWriter):
  tag = 'tr'

class Title(HtmlWriter):
  tag = 'title'

