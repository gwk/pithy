# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Developer reference page demonstrating all standard HTML form controls using traditional forms.'

from inspect import get_annotations
from typing import Any

from ....default import Default
from ....html import Div, Form, H1, Input, Label, Main, Select, Span, Strong, TextArea
from ....markup import MuChild
from ...endpoint import Endpoint, NoFields
from ...request import Request, UploadedFile
from ...response import Response
from ..pages import dev_page


class DevControlsForm(Endpoint):
  'Demonstrates form controls.'

  max_body_bytes = 4096

  class Post:
    # Native form submission always sends text-like controls, possibly empty.
    text:str
    email:str
    hidden:str
    number:str
    password:str
    tel:str
    url:str
    search:str
    textarea:str
    date:str
    time:str
    datetime_local:str
    color:str
    range:str
    checkbox:bool # pithy.js sends 'true' or 'false' for a bool checkbox; see `Input.bool_checkbox`.
    checkbox_set:list[str] # pithy.js sends the NUL marker for an empty set, which fills the field as the empty list.
    radio:str|None # A radio group with no selection is not sent.
    select:str|None # The disabled placeholder option is not sent.
    select_multiple:list[str]|None # A multiple select with no selection is not sent.
    file:UploadedFile|None # An empty file input is skipped by the multipart parser.

  def get(self, request:Request, fields:NoFields) -> Response:
    return controls_page({})

  def post(self, request:Request, fields:Post) -> Response:
    return controls_page(posted_items(fields))


def posted_items(fields:DevControlsForm.Post) -> dict[str,str|list[str]]:
  'Display values for the posted fields, omitting absent and empty-string values; an empty list is kept.'
  items:dict[str,str|list[str]] = {}
  for name in get_annotations(DevControlsForm.Post):
    val = getattr(fields, name)
    if val is None or val == '': continue
    if isinstance(val, bool): val = 'true' if val else 'false'
    elif isinstance(val, UploadedFile): val = f'{val.filename} ({len(val.data)} bytes)'
    items[name] = val
  return items


def controls_page(values:dict[str,str|list[str]]) -> Response:
  main = Main(
    H1('Form Controls'),
    Div(cl='controls-demo-layout', _=[
      controls_form(values),
      posted_values_div(values),
    ]))
  return dev_page(title='Form Controls', main=main,
    breadcrumbs=[('/', 'Home'), ('/form', 'Form'), ('/form/controls', 'Controls')])


def controls_form(values:dict[str,str|list[str]]|None=None) -> Div:
  'Build a Form demonstrating all standard interactive HTML form controls, optionally populated with `values`.'

  vals:dict[str,str|list[str]] = values or {}
  div = Div()
  form = div.append(Form(cl='grid', method='post', enctype='multipart/form-data'))

  def _row(label_text:str, *controls:MuChild) -> None:
    'Append a label and control(s) to the form grid.'
    for control in controls:
      form.append(Label(_=label_text))
      form.append(control)

  def _v(name:str) -> Any:
    'Return a dict with value key if `name` is in `vals`, for use as kwargs.'
    v = vals.get(name)
    return {'value': v} if v is not None else {}

  form.append(Input(type='hidden', name='hidden', value=vals.get('hidden', 'hidden-value')))

  _row('text', Input(type='text', name='text', placeholder='text input', **_v('text')))
  _row('email', Input(type='email', name='email', placeholder='user@example.com', **_v('email')))
  _row('number', Input(type='number', name='number', placeholder='0', **_v('number')))
  _row('password', Input(type='password', name='password', placeholder='password', **_v('password')))
  _row('tel', Input(type='tel', name='tel', placeholder='+1-555-555-5555', **_v('tel')))
  _row('url', Input(type='url', name='url', placeholder='https://example.com', **_v('url')))
  _row('search', Input(type='search', name='search', placeholder='search...', **_v('search')))
  _row('textarea', TextArea(name='textarea', placeholder='Enter text here...', rows='4',
    _=vals.get('textarea', '')))

  _row('checkbox', Input.bool_checkbox(name='checkbox', is_checked=(vals.get('checkbox') == 'true')))

  _row('checkbox set', Span(cl='flex-row gap-1ch').labeled_checkboxes('checkbox_set', require_one=False,
    choices={'a' : 'Option A', 'b' : 'Option B', 'c' : 'Option C'}, checked=vals.get('checkbox_set', ())))

  _row('radio', Span(cl='flex-row gap-1ch').labeled_radios('radio', is_opt=True,
    checked=vals.get('radio', Default._), choices={'a' : 'Option A', 'b' : 'Option B'}))

  _row('select', Select(name='select').options(['Option A', 'Option B', 'Option C'],
    placeholder='Choose...', value=vals.get('select')))

  _row('select multiple',
    Select(name='select_multiple', multiple='').options(['Option A', 'Option B', 'Option C'],
      value=vals.get('select_multiple')))

  _row('date', Input(type='date', name='date', **_v('date')))
  _row('time', Input(type='time', name='time', **_v('time')))
  _row('datetime_local', Input(type='datetime-local', name='datetime_local', **_v('datetime_local')))

  _row('color', Input(type='color', name='color', **_v('color')))

  _row('range', Span(cl='flex-row gap-1ch',
    _=['0', Input(type='range', name='range', min='0', max='10', **_v('range')), '10']))

  _row('file', Input(type='file', name='file'))

  _row('reset', Input(type='reset', value='Reset'))
  _row('submit', Input(type='submit', value='Submit'))

  return div


def posted_values_div(values:dict[str,str|list[str]]|None=None) -> Div:
  'Build a panel that reports POST values.'
  if not values:
    return Div(id='posted-values', cl='panel muted', _='No values posted yet. Fill in some fields and submit.')
  return Div(id='posted-values', cl='panel flow flow-tight',
    _=[Div(Strong(k), f': {v}') for k, v in values.items()])
