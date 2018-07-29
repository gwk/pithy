# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
HTML writer.
'''

from sys import stdout
from html import escape as html_escape
from types import TracebackType
from typing import Any, ContextManager, Dict, List, Optional, Sequence, TextIO, Tuple, Type, Union, Iterable, cast
from .num import Num, NumRange
from .xml import XmlAttrs, XmlWriter, add_opt_attrs, esc_xml_attr, esc_xml_text, _Self
from .svg import *


Dim = Union[int, float, str]
Vec = Tuple[Num, Num]
VecOrNum = Union[Vec, Num]
PathCommand = Tuple

ViewBox = Union[None, Vec, Tuple[Num, Num, Num, Num], Tuple[Vec, Vec]] # TODO: currently unused.


class HtmlWriter(XmlWriter):
  '''
  HtmlWriter is a ContextManager class that outputs SVG code to a file (stdout by default).
  Like its parent class XmlWriter, it uses the __enter__ and __exit__ methods to automatically output open and close tags.
  '''

  def __init__(self, file:TextIO=None, attrs:XmlAttrs=None, **extra_attrs:Any) -> None:
    self.write_raw('<!DOCTYPE html>')
    super().__init__(tag='html', file=file, attrs=attrs, **extra_attrs)

  def body(self, **attrs:Any) -> XmlWriter:
    return self.sub('body', attrs=attrs)

  def br(self) -> None: self.leaf('br', attrs=None)

  def div(self, **attrs:Any) -> XmlWriter: return self.sub('div', attrs=attrs)

  def head(self, **attrs:Any) -> XmlWriter: return self.sub('head', attrs=attrs)

  def h1(self, text:str, **attrs:Any) -> None: self.leaf_text('h1', attrs=attrs, text=text)
  def h2(self, text:str, **attrs:Any) -> None: self.leaf_text('h2', attrs=attrs, text=text)
  def h3(self, text:str, **attrs:Any) -> None: self.leaf_text('h3', attrs=attrs, text=text)
  def h4(self, text:str, **attrs:Any) -> None: self.leaf_text('h4', attrs=attrs, text=text)
  def h5(self, text:str, **attrs:Any) -> None: self.leaf_text('h5', attrs=attrs, text=text)
  def h6(self, text:str, **attrs:Any) -> None: self.leaf_text('h6', attrs=attrs, text=text)

  def hr(self) -> None: self.leaf('hr', attrs=None)

  def meta(self, **attrs:Any) -> XmlWriter: return self.sub('meta', attrs=attrs)

  def p(self, **attrs:Any) -> XmlWriter: return self.sub('p', attrs=attrs)

  def style(self, *styles:str, **attrs:Any) -> None:
    self.leaf_text('style', attrs=attrs, text='\n'.join(styles))

  def svg(self, pos:Vec=None, size:VecOrNum=None, *, x:Dim=None, y:Dim=None, w:Dim=None, h:Dim=None,
   vx:Num=0, vy:Num=0, vw:Num=None, vh:Num=None, **attrs:Any) -> SvgWriter:
    return SvgWriter(file=self.file, pos=pos, size=size, x=x, y=y, w=w, h=h, vx=vx, vy=vy, vw=vw, vh=vh, **attrs)

  # Forms.

  def form(self, **attrs:Any) -> XmlWriter: return self.sub('form', attrs=attrs)

  def input(self, type:str, **attrs:Any) -> None:
    assert type in form_input_types
    attrs['type'] = type
    return self.leaf('input', attrs=attrs)

  def input_submit(self, **attrs:Any) -> None:
    attrs['type'] = 'submit'
    return self.leaf('input', attrs=attrs)

  def input_text(self, **attrs:Any) -> None:
    attrs['type'] = 'text'
    return self.leaf('input', attrs=attrs)

  def label(self, text:str, **attrs:Any) -> None:
    return self.leaf_text('label', text=text, attrs=attrs)

  # Tables.

  # TODO: return XmlWriter subclasses that enforce correct permitted parent/child structures.

  def table(self, **attrs:Any) -> XmlWriter: return self.sub('table', attrs=attrs)

  def caption(self, **attrs:Any) -> XmlWriter: return self.sub('caption', attrs=attrs)

  def thead(self, **attrs:Any) -> XmlWriter: return self.sub('thead', attrs=attrs)

  def tfoot(self, **attrs:Any) -> XmlWriter: return self.sub('tfoot', attrs=attrs)

  def td(self, **attrs:Any) -> XmlWriter: return self.sub('td', attrs=attrs)

  def th(self, **attrs:Any) -> XmlWriter: return self.sub('th', attrs=attrs)

  def tr(self, *cell_contents:Any, **attrs:Any) -> XmlWriter:
    s = self.sub('tr', attrs=attrs)
    for c in cell_contents:
      if isinstance(c, TD):
        with self.td(**c.attrs): self.write(c.contents)
      elif isinstance(c, TH):
        with self.th(**c.attrs): self.write(c.contents)
      else:
        with self.td(): self.write(c)
    return s

  def tr_th(self, *header_contents:Any, **attrs:Any) -> XmlWriter:
    s = self.sub('tr', attrs=attrs)
    for c in header_contents:
      with self.th(): self.write(c)
    return s

  def title(self, title:str, **attrs:Any) -> None:
    self.leaf_text('title', attrs=attrs, text=title)


class TD:
  def __init__(self, contents:Any, **attrs:Any) -> None:
    self.contents = contents
    self.attrs = attrs

class TH:
  def __init__(self, contents:Any, **attrs:Any) -> None:
    self.contents = contents
    self.attrs = attrs


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
