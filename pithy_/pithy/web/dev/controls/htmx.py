# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Developer reference page demonstrating all standard HTML form controls using HTMX.'

import datetime as dt
from typing import Any

from ....html import A, Div, Form, H1, Input, Label, Li, Main, Ol, Select, Span, Strong, Sup, TextArea
from ....markup import MuChild
from ...endpoint import Endpoint, NoFields
from ...request import Request, UploadedFile
from ...response import HtmlResponse, Response
from ..pages import page_html


class DevControlsHtmx(Endpoint):
  'Demonstrates HTMX controls.'
  max_body_bytes = 1024 * 64

  def handle_endpoint(self, request:Request, fields:NoFields) -> Response:
    main = Main(
      H1('HTMX Controls'),
      posted_values_div(),
      controls_htmx())
    return page_html(title='Dev Controls', breadcrumbs=[('/', 'Home'), ('/controls', 'Controls'), ('/controls/htmx', 'HTMX')],
      main=main)


def posted_values_div(values:dict[str,str|list[str]]|None=None) -> Div:
  return Div(style='background-color: #f0f4ff; padding: 1rem;', *[Div(Strong(k), f': {v}') for k, v in (values or {}).items()], id='posted-values')



class ControlsHtmxUpdate(Endpoint):
  'Handles any field update from the HTMX DevControls page.'
  methods = 'POST'
  max_body_bytes = 64 * 1024

  class Fields:
    text: str | None
    email: str | None
    number: str | None
    password: str | None
    tel: str | None
    url: str | None
    search: str | None
    textarea: str | None
    checkbox: str | None
    radio: str | None
    select: str | None
    date: dt.date | None
    time: dt.time | None
    datetime_local: dt.datetime | None
    month: str | None
    week: str | None
    color: str | None
    range: int | None
    select_multiple: list[str] | None
    file: UploadedFile | None

  def handle_endpoint(self, request:Request, fields:Fields) -> Response:
    for name in self._fields:
      val = getattr(fields, name)
      if val is None:
        continue
      display = name.replace('_', '-')
      if isinstance(val, UploadedFile):
        return HtmlResponse(body=Div(Strong(display), f': {val.filename} ({len(val.data)} bytes)'))
      return HtmlResponse(body=Div(Strong(display), f': {val}'))
    return HtmlResponse(body=Div())



def controls_htmx() -> Div:
  'Return a Form demonstrating all standard interactive HTML form controls, with HTMX.'

  outer = Div()
  div = outer.append(Div(cl='form_grid'))
  url = '/controls/htmx/update.htmx'
  # The update endpoint returns a complete replacement for the panel, so swap the element itself, not its contents.
  _htmx_tags:dict[str,Any] = {'hx_target': '#posted-values', 'hx_swap': 'outerHTML'}

  def _row(label_text:str, *controls:MuChild) -> None:
    'Append a label and control(s) to the form grid.'
    for control in controls:
      div.append(Label(_=label_text))
      div.append(control)

  def ftnt(i:int) -> Sup:
    'Footnote link.'
    return Sup(_=['[', A(href=f'#fn{i}', _=i), ']'])

  _row('text', Input(type='text', name='text', placeholder='text input', hx_trigger="change", hx_post=url, **_htmx_tags))
  _row('email', Input(type='email', name='email', placeholder='user@example.com', hx_trigger="change", hx_post=url, **_htmx_tags))
  _row('number', Input(type='number', name='number', placeholder='0', hx_trigger="change", hx_post=url, **_htmx_tags))
  _row('password', Input(type='password', name='password', placeholder='password', hx_trigger="change", hx_post=url, **_htmx_tags))
  _row('tel', Input(type='tel', name='tel', placeholder='+1-555-555-5555', hx_trigger="change", hx_post=url, **_htmx_tags))
  _row('url', Input(type='url', name='url', placeholder='https://example.com', hx_trigger="change", hx_post=url, **_htmx_tags))
  _row('search', Input(type='search', name='search', placeholder='search', hx_trigger="change", hx_post=url, **_htmx_tags))
  _row('textarea', TextArea(name='textarea', placeholder='Enter text here...', rows='4', cols='40', hx_trigger="change", hx_post=url, **_htmx_tags))

  # Checkboxes must be wrapped in a <form> so HTMX uses form serialization, which omits the field when unchecked.
  # Without a form ancestor, HTMX reads input.value, which is always "on" regardless of checked state.
  _row('checkbox', Span(cl='flex-row gap-1ch',
    _=[Form(hx_post=url, hx_trigger='change', **_htmx_tags,
      _=Input(type='checkbox', name='checkbox')), ftnt(1)]))

  _row('radio', Span(cl='flex-row gap-1ch',
    _=[
      Label(Input(type='radio', name='radio', value='a', hx_trigger='change', hx_post=url, **_htmx_tags), 'Option A'),
      Label(Input(type='radio', name='radio', value='b', hx_trigger='change', hx_post=url, **_htmx_tags), 'Option B'),
    ]))

  _row('select', Select(name='select', hx_trigger='change', hx_post=url, **_htmx_tags).options(['Option A', 'Option B', 'Option C'],
    placeholder='Choose...'))

  # Select-multiple inputs must be wrapped in a <form> so HTMX uses form serialization, which captures all selected values.
  # Without a form ancestor, HTMX reads input.value, which returns only the first selected option rather than iterating input.selectedOptions.
  _row('select multiple', Span(cl='flex-row gap-1ch',
    _=[Form(hx_post=url, hx_trigger='change delay:500ms', **_htmx_tags,
      _=Select(name='select_multiple', multiple='').options(['Option A', 'Option B', 'Option C'])), ftnt(2)]))

  _row('date', Input(type='date', name='date', hx_trigger='change', hx_post=url, **_htmx_tags))
  _row('time', Input(type='time', name='time', hx_trigger='change', hx_post=url, **_htmx_tags))
  _row('datetime_local', Span(cl='flex-row gap-1ch',
    _=[Input(type='datetime-local', name='datetime_local', hx_trigger='change', hx_post=url, **_htmx_tags), ftnt(3)]))
  _row('month', Span(cl='flex-row gap-1ch', _=[Input(type='month', name='month', hx_trigger='change', hx_post=url, **_htmx_tags), ftnt(3)]))
  _row('week', Span(cl='flex-row gap-1ch', _=[Input(type='week', name='week', hx_trigger='change', hx_post=url, **_htmx_tags), ftnt(3)]))


  _row('color', Input(type='color', name='color', hx_trigger='change', hx_post=url, **_htmx_tags))

  _row('range', Input(type='range', name='range', min='0', max='10', hx_trigger='input', hx_post=url, **_htmx_tags))


  # HTMX reads .value off the triggering element, except when it finds a <form> ancestor,
  # in which case it uses the JS FormData API (which handles checkboxes, files, etc. correctly).
  #
  # File inputs must be wrapped in a <form> because only FormData reads input.files (the actual
  # binary file handle); without it, HTMX falls back to input.value, which is just a fake path string.
  _row('file', Span(cl='flex-row gap-1ch',
    _=[Form(hx_encoding='multipart/form-data', hx_post=url, hx_trigger='change', **_htmx_tags,
      _=Input(type='file', name='file')), ftnt(4)]))

  outer.append(Div(cl='flex-col font-small', _=['Notes:',
  Ol(
    Li(id='fn1', _='Checkboxes must be wrapped in a <form> so HTMX uses form serialization, which omits the field when'
      ' unchecked. Without a form ancestor, HTMX reads input.value, which is always "on" regardless of checked state.'),
    Li(id='fn2', _='Select-multiple inputs must be wrapped in a <form> so HTMX uses form serialization, which captures'
      ' all selected values. Without a form ancestor, HTMX reads input.value, which returns only the first selected'
      ' option rather than iterating input.selectedOptions.'),
    Li(id='fn3', _='Desktop Safari falls back to a plain text field for datetime-local, month, and week input types.'
      ' Values entered in the text fallback are not validated by the browser.'),
    Li(id='fn4', _='File inputs must be wrapped in a <form> so HTMX uses the FormData API, which reads the actual file'
      ' bytes via input.files. Without a form ancestor, HTMX falls back to input.value, which is a fake path string.'),
  )]))

  return outer
