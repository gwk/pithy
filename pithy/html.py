# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
HTML writer.
'''

from sys import stdout
from html import escape as html_escape
from types import TracebackType
from typing import Any, ContextManager, Dict, List, Optional, Sequence, TextIO, Tuple, Type, Union, Iterable, cast
from .num import Num, NumRange
from .xml import XmlAttrs, XmlWriter, add_opt_attrs, esc_xml_attr, esc_xml_text, _XmlWriter
from .svg import *


Dim = Union[int, float, str]
Vec = Tuple[Num, Num]
VecOrNum = Union[Vec, Num]
PathCommand = Tuple

ViewBox = Union[None, Vec, Tuple[Num, Num, Num, Num], Tuple[Vec, Vec]] # TODO: currently unused.


class HtmlWriter(XmlWriter):
  '''
  HtmlWriter is a ContextManager class that outputs HTML code to a file (stdout by default).
  Like its parent class XmlWriter, it uses the __enter__ and __exit__ methods to automatically output open and close tags.
  '''

  can_auto_close_tags = False # Unlike XML, HTML5 dictates that each tag type either be self-closing or not.

  def br(self) -> None: self.leaf('br', attrs=None)

  def div(self, *children:Any, **attrs:Any) -> 'Div': return self.child(Div, *children, attrs=attrs)

  def h1(self, *children:Any, **attrs:Any) -> 'H1': return self.child(H1, *children, attrs=attrs)
  def h2(self, *children:Any, **attrs:Any) -> 'H2': return self.child(H2, *children, attrs=attrs)
  def h3(self, *children:Any, **attrs:Any) -> 'H3': return self.child(H3, *children, attrs=attrs)
  def h4(self, *children:Any, **attrs:Any) -> 'H4': return self.child(H4, *children, attrs=attrs)
  def h5(self, *children:Any, **attrs:Any) -> 'H5': return self.child(H5, *children, attrs=attrs)
  def h6(self, *children:Any, **attrs:Any) -> 'H6': return self.child(H6, *children, attrs=attrs)

  def hr(self) -> None: self.leaf('hr', attrs=None)

  def meta(self, **attrs:Any) -> None: return self.leaf(tag='meta', attrs=attrs)

  def p(self, *children:Any, **attrs:Any) -> 'P': return self.child(P, *children, attrs=attrs)

  def style(self, *children:Any, **attrs:Any) -> 'Style': return self.child(Style, *children, attrs=attrs)

  def svg(self, *children:Any, **kwargs:Any) -> Svg:
    return self.child(Svg, *children, **kwargs)

  # Forms.

  def form(self, *children:Any, **attrs:Any) -> 'Form': return self.child(Form, *children, attrs=attrs)

  def input(self, **attrs:Any) -> None:
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


class Body(HtmlWriter):
  tag = 'body'

class Div(HtmlWriter):
  tag = 'div'

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

class Style(HtmlWriter):
  tag = 'style'

class Form(HtmlWriter):
  tag = 'form'

class Input(HtmlWriter):
  tag = 'input'

class Label(HtmlWriter):
  tag = 'label'

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


form_input_types = frozenset({
  'button', # push button with no default behavior.
  'checkbox', # check box allowing single values to be selected/deselected.
  'color', # control for specifying a color. A color picker's UI has no required features other than accepting simple colors as text (more info).
  'date', # control for entering a date (year, month, and day, with no time).
  'datetime-local', # control for entering a date and time, with no time zone.
  'email', # field for editing an e-mail address.
  'file', # control that lets the user select a file. Use `accept` to define the types of files that the control can select.
  'hidden', # control that is not displayed but whose value is submitted to the server.
  'image', # graphical submit button. `src` specifies the image and `alt` specifies alternative text. Use the height and width attributes to define the size of the image in pixels.
  'month', # control for entering a month and year, with no time zone.
  'number', # control for entering a number.
  'password', # single-line text field whose value is obscured. Use the maxlength and minlength attributes to specify the maximum length of the value that can be entered.
  'radio', # radio button, allowing a single value to be selected out of multiple choices.
  'range', # control for entering a number whose exact value is not important.
  'reset', # button that resets the contents of the form to default values.
  'search', # single-line text field for entering search strings. Line-breaks are automatically removed from the input value.
  'submit', # button that submits the form.
  'tel', # control for entering a telephone number.
  'text', # single-line text field. Line-breaks are automatically removed from the input value.
  'time', # control for entering a time value with no time zone.
  'url', # field for entering a URL.
  'week', # control for entering a date consisting of a week-year number and a week number with no time zone.
})
