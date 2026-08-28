# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Developer reference page demonstrating all standard HTML form controls using traditional forms.'

from typing import Any

from ....default import Default
from ....html import Div, Form, H1, H2, Input, Label, Main, P, Select, Span, Strong, TextArea
from ....markup import MuChild, Present
from ...endpoint import Endpoint
from ...request import Request, UploadedFile
from ...response import Response
from ..pages import dev_page


class DevControlsForm(Endpoint):
  'Demonstrates form controls.'

  methods = ('GET', 'POST')
  max_body_bytes = 64 * 1024

  class Fields:
    text: str | None
    email: str | None
    hidden: str | None
    number: str | None
    password: str | None
    tel: str | None
    url: str | None
    search: str | None
    textarea: str | None
    checkbox: str | None
    radio: str | None
    select: str | None
    date: str | None
    time: str | None
    color: str | None
    range: str | None
    submit: str | None
    week: str | None
    month: str | None
    datetime_local: str | None
    select_multiple: list[str] | None
    file: UploadedFile | None

  def _items(self, fields:Fields) -> dict[str, str | list[str]]:
    return {name: v for name in self._fields if (v := getattr(fields, name))}

  def handle_endpoint(self, request:Request, fields:Fields) -> Response:
    values = self._items(fields)
    main = Main(
      H1('Form Controls'),
      Div(cl='controls-demo-layout', _=[
        controls_form(values),
        posted_values_div(values),
      ]))
    return dev_page(title='Form Controls', main=main,
      breadcrumbs=[('/', 'Home'), ('/controls', 'Controls'), ('/controls/form', 'Form')])


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

  _row('checkbox', Input(type='checkbox', name='checkbox', checked=Present('checkbox' in vals)))

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

  _row('button', Input(type='button', value='Button'))
  _row('image', Span(Input(type='image', src='', alt='Submit image'), ' (A button with a custom image)'))

  form.append(Div(cl='controls-section flow flow-tight', _=[
    H2('Not portable across target browsers'),
    P('These controls fall back to plain text fields in desktop Safari.'),
  ]))
  _row('month', Input(type='month', name='month', **_v('month')))
  _row('week', Input(type='week', name='week', **_v('week')))
  form.append(Div(cl='controls-section-end'))

  _row('reset', Input(type='reset', value='Reset'))
  _row('submit', Input(type='submit', value='Submit'))

  return div


def posted_values_div(values:dict[str,str|list[str]]|None=None) -> Div:
  'Build a panel that reports POST values.'
  if not values:
    return Div(id='posted-values', cl='panel muted', _='No values posted yet. Fill in some fields and submit.')
  return Div(id='posted-values', cl='panel flow flow-tight',
    _=[Div(Strong(k), f': {v}') for k, v in values.items()])
