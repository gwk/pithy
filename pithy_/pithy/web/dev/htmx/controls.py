# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Developer reference page demonstrating all standard HTML form controls using HTMX.'

import datetime as dt
from typing import Any

from ....html import A, Div, H1, Input, Label, Li, Main, Ol, Select, Span, Strong, Sup, TextArea
from ....markup import MuChild
from ...endpoint import Endpoint, NoFields
from ...request import Request, UploadedFile
from ...response import HtmlResponse, Response
from ..pages import dev_page


class DevControlsHtmx(Endpoint):
  'Demonstrates HTMX controls.'
  max_body_bytes = 4096

  def handle_endpoint(self, request:Request, fields:NoFields) -> Response:
    main = Main(
      H1('HTMX Controls'),
      Div(cl='controls-demo-layout', _=[
        controls_htmx(),
        posted_values_div(),
      ]))
    return dev_page(title='HTMX Controls', main=main,
      breadcrumbs=[('/', 'Home'), ('/htmx', 'HTMX'), ('/htmx/controls', 'Controls')])


def posted_values_div(values:dict[str,str|list[str]]|None=None) -> Div:
  'Return the panel that htmx swaps the most recent field update into.'
  if not values:
    return Div(id='posted-values', cl='panel muted', _='No updates yet. Change a control to post it.')
  return Div(id='posted-values', cl='panel flow flow-tight',
    _=[Div(Strong(k), f': {v}') for k, v in values.items()])



class ControlsHtmxUpdate(Endpoint):
  'Handles any field update from the HTMX DevControls page.'
  methods = 'POST'
  max_body_bytes = 4096

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
    checkbox_set: list[str] | None
    radio: str | None
    select: str | None
    date: dt.date | None
    time: dt.time | None
    datetime_local: dt.datetime | None
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
        val = f'{val.filename} ({len(val.data)} bytes)'
      return HtmlResponse(body=posted_values_div({display: str(val)}))
    return HtmlResponse(body=posted_values_div())



def controls_htmx() -> Div:
  'Return a grid of the standard interactive HTML form controls, each posting its own updates with htmx.'

  outer = Div()
  div = outer.append(Div(cl='form_grid'))
  url = '/htmx/controls/update.htmx'
  # The update endpoint returns a complete replacement for the panel, so swap the element itself, not its contents.
  _htmx_tags:dict[str,Any] = {'hx_target': '#posted-values', 'hx_swap': 'outerHTML'}

  def _row(label_text:str, *controls:MuChild) -> None:
    'Append a label and control(s) to the form grid.'
    for control in controls:
      div.append(Label(_=label_text))
      div.append(control)

  def ftnt(i:int) -> Sup:
    'Footnote link.'
    return Sup(cl='footnote-ref', _=A(href=f'#fn{i}', _=f'[{i}]'))

  _row('text', Input(type='text', name='text', placeholder='text input', hx_trigger="change", hx_post=url, **_htmx_tags))
  _row('email', Input(type='email', name='email', placeholder='user@example.com', hx_trigger="change", hx_post=url, **_htmx_tags))
  _row('number', Input(type='number', name='number', placeholder='0', hx_trigger="change", hx_post=url, **_htmx_tags))
  _row('password', Input(type='password', name='password', placeholder='password', hx_trigger="change", hx_post=url, **_htmx_tags))
  _row('tel', Input(type='tel', name='tel', placeholder='+1-555-555-5555', hx_trigger="change", hx_post=url, **_htmx_tags))
  _row('url', Input(type='url', name='url', placeholder='https://example.com', hx_trigger="change", hx_post=url, **_htmx_tags))
  _row('search', Input(type='search', name='search', placeholder='search', hx_trigger="change", hx_post=url, **_htmx_tags))
  _row('textarea', TextArea(name='textarea', placeholder='Enter text here...', rows='4', hx_trigger="change", hx_post=url, **_htmx_tags))

  _row('checkbox', Span(cl='flex-row gap-1ch',
    _=[Input.bool_checkbox(is_checked=False, name='checkbox', hx_trigger='change', hx_post=url, **_htmx_tags), ftnt(1)]))

  # The containing span is the htmx source, so every member of the set is sent on each change.
  _row('checkbox set', Span(cl='flex-row gap-1ch', _=[
    Span(cl='flex-row gap-1ch', hx_trigger='change', hx_post=url, **_htmx_tags).labeled_checkboxes('checkbox_set',
      require_one=False, choices={'a' : 'Option A', 'b' : 'Option B', 'c' : 'Option C'}),
    ftnt(1)]))

  _row('radio', Span(cl='flex-row gap-1ch',
    _=[
      Label(Input(type='radio', name='radio', value='a', hx_trigger='change', hx_post=url, **_htmx_tags), 'Option A'),
      Label(Input(type='radio', name='radio', value='b', hx_trigger='change', hx_post=url, **_htmx_tags), 'Option B'),
    ]))

  _row('select', Select(name='select', hx_trigger='change', hx_post=url, **_htmx_tags).options(['Option A', 'Option B', 'Option C'],
    placeholder='Choose...'))

  _row('select multiple', Select(name='select_multiple', multiple='', hx_trigger='change delay:500ms', hx_post=url,
    **_htmx_tags).options(['Option A', 'Option B', 'Option C']))

  _row('date', Input(type='date', name='date', hx_trigger='change', hx_post=url, **_htmx_tags))
  _row('time', Input(type='time', name='time', hx_trigger='change', hx_post=url, **_htmx_tags))
  _row('datetime_local', Input(type='datetime-local', name='datetime_local', hx_trigger='change', hx_post=url, **_htmx_tags))

  _row('color', Input(type='color', name='color', hx_trigger='change', hx_post=url, **_htmx_tags))

  _row('range', Span(cl='flex-row gap-1ch', _=[
    '0', Input(type='range', name='range', min='0', max='10', hx_trigger='input', hx_post=url, **_htmx_tags), '10']))


  # File inputs need `hx-encoding` for the file bytes to be sent; the default urlencoded body stringifies the File object.
  _row('file', Span(cl='flex-row gap-1ch', _=[
    Input(type='file', name='file', hx_encoding='multipart/form-data', hx_trigger='change', hx_post=url, **_htmx_tags), ftnt(2)]))

  outer.append(Div(cl='flex-col font-small', _=['Notes:',
  Ol(
    Li(id='fn1', _='HTML sends a checkbox only when it is checked, so an unchecked box is indistinguishable from an'
      ' absent field. Input.bool_checkbox marks the control with data-pithy-checkbox="bool" so pithy.js sends "true"'
      ' or "false" for native form submission, htmx requests, and hx-include. labeled_checkboxes marks set members'
      ' with data-pithy-checkbox="set";'
      ' pithy.js sends a single NUL character for the set name when no member is checked, which endpoint list fields'
      ' accept as the empty list. Unmarked checkboxes retain native submission behavior.'),
    Li(id='fn2', _='File inputs need hx-encoding="multipart/form-data". With the default urlencoded body the File object'
      ' is stringified to "[object File]". A wrapping <form> is not required; htmx 4 reads input.files directly.'),
  )]))

  return outer
