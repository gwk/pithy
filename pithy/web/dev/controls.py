# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Developer reference page demonstrating all standard HTML form controls with htmx.'

from typing import Any

from pithy.default import Default
from pithy.html import A, Div, Form, Input, Label, Li, Ol, Select, Span, Sup, TextArea
from pithy.markup import MuChild, Present


def controls_form(values:dict[str,str]|None=None) -> Div:
  'Return a Form demonstrating all standard interactive HTML form controls, optionally populated with `values`.'

  vals:dict[str,str] = values or {}
  div = Div()
  form = div.append(Form(cl='grid', method='post', enctype='multipart/form-data'))

  def _row(label_text:str, *controls:MuChild) -> None:
    'Append a label and control(s) to the form grid.'
    for control in controls:
      form.append(Label(_=label_text))
      form.append(control)

  def ftnt(i:int) -> Sup:
    'Footnote link.'
    return Sup(_=['[', A(href=f'#fn{i}', _=i), ']'])

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
  _row('textarea', TextArea(name='textarea', placeholder='Enter text here...', rows='4', cols='40',
    _=vals.get('textarea', '')))

  _row('checkbox', Input(type='checkbox', name='checkbox', checked=Present('checkbox' in vals)))

  _row('radio', Span(cl='flex-row gap-1ch').labeled_radios('radio', is_opt=True,
    checked=vals.get('radio', Default._), choices={'a' : 'Option A', 'b' : 'Option B'}))

  _row('select', Select(name='select').options(['Option A', 'Option B', 'Option C'],
    placeholder='Choose...', value=vals.get('select')))

  _row('select multiple',
    Select(name='select-multiple', multiple='').options(['Option A', 'Option B', 'Option C'],
      value=vals.get('select-multiple')))

  _row('date', Input(type='date', name='date', **_v('date')))
  _row('time', Input(type='time', name='time', **_v('time')))
  _row('datetime-local', Span(cl='flex-row gap-1ch',
    _=[Input(type='datetime-local', name='datetime-local', **_v('datetime-local')), ftnt(1)]))
  _row('month', Span(cl='flex-row gap-1ch', _=[Input(type='month', name='month', **_v('month')), ftnt(1)]))
  _row('week', Span(cl='flex-row gap-1ch', _=[Input(type='week', name='week', **_v('week')), ftnt(1)]))


  _row('color', Input(type='color', name='color', **_v('color')))

  _row('range', Input(type='range', name='range', min='0', max='10', **_v('range')))


  _row('file', Input(type='file', name='file'))

  _row('button', Input(type='button', value='Button'))
  _row('image', Span(Input(type='image', src='', alt='Submit image'), ' (A button with a custom image)'))

  _row('reset', Input(type='reset', value='Reset'))
  _row('submit', Input(type='submit', value='Submit'))

  div.append(Div(cl='flex-col font-small', _=['Notes:',
  Ol(
    Li(id='fn1', _='Desktop Safari falls back to a plain text field for datetime-local, month, and week input types.'
      ' Values entered in the text fallback are not validated by the browser.'),
  )]))

  return div
