# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Developer reference page demonstrating all standard HTML form controls with and without htmx.'

from typing import Any

from pithy.default import Default
from pithy.html import A, Div, Form, Input, Label, Li, Ol, Select, Span, Strong, Sup, TextArea
from pithy.markup import MuChild, Present


def posted_values(values:dict[str,str|list[str]]|None=None) -> Div:
  return Div(style='background-color: #f0f4ff; padding: 1rem;', *[Div(Strong(k), f': {v}') for k, v in (values or {}).items()], id='posted-values')

def controls_form(values:dict[str, str | list[str]]|None=None) -> Div:
  'Return a Form demonstrating all standard interactive HTML form controls, optionally populated with `values`.'

  vals:dict[str, str | list[str]] = values or {}
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
    Select(name='select_multiple', multiple='').options(['Option A', 'Option B', 'Option C'],
      value=vals.get('select-multiple')))

  _row('date', Input(type='date', name='date', **_v('date')))
  _row('time', Input(type='time', name='time', **_v('time')))
  _row('datetime_local', Span(cl='flex-row gap-1ch',
    _=[Input(type='datetime-local', name='datetime_local', **_v('datetime_local')), ftnt(1)]))
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

def controls_htmx() -> Div:
  'Return a Form demonstrating all standard interactive HTML form controls, with HTMX.'

  div = Div(cl='form_grid')
  _htmx_tags:dict[str,Any] = {'hx_target': '#posted-values', 'hx_swap': 'beforeend'}


  def _row(label_text:str, *controls:MuChild) -> None:
    'Append a label and control(s) to the form grid.'
    for control in controls:
      div.append(Label(_=label_text))
      div.append(control)

  def ftnt(i:int) -> Sup:
    'Footnote link.'
    return Sup(_=['[', A(href=f'#fn{i}', _=i), ']'])

  _row('text', Input(type='text', name='text', placeholder='text input', hx_trigger="change", hx_post='/controls-htmx/text', **_htmx_tags))
  _row('email', Input(type='email', name='email', placeholder='user@example.com', hx_trigger="change", hx_post='/controls-htmx/email', **_htmx_tags))
  _row('number', Input(type='number', name='number', placeholder='0', hx_trigger="change", hx_post='/controls-htmx/number', **_htmx_tags))
  _row('password', Input(type='password', name='password', placeholder='password', hx_trigger="change", hx_post='/controls-htmx/password', **_htmx_tags))
  _row('tel', Input(type='tel', name='tel', placeholder='+1-555-555-5555', hx_trigger="change", hx_post='/controls-htmx/tel', **_htmx_tags))
  _row('url', Input(type='url', name='url', placeholder='https://example.com', hx_trigger="change", hx_post='/controls-htmx/url', **_htmx_tags))
  _row('search', Input(type='search', name='search', placeholder='search', hx_trigger="change", hx_post='/controls-htmx/search', **_htmx_tags))
  _row('textarea', TextArea(name='textarea', placeholder='Enter text here...', rows='4', cols='40', hx_trigger="change", hx_post='/controls-htmx/textarea', **_htmx_tags))

  # Checkboxes must be wrapped in a <form> so HTMX uses form serialization, which omits the field when unchecked.
  # Without a form ancestor, HTMX reads input.value, which is always "on" regardless of checked state.
  _row('checkbox', Span(cl='flex-row gap-1ch',
    _=[Form(hx_post='/controls-htmx/checkbox', hx_trigger='change', **_htmx_tags,
      _=Input(type='checkbox', name='checkbox')), ftnt(1)]))

  _row('radio', Span(cl='flex-row gap-1ch',
    _=[
      Label(Input(type='radio', name='radio', value='a', hx_trigger='change', hx_post='/controls-htmx/radio', **_htmx_tags), 'Option A'),
      Label(Input(type='radio', name='radio', value='b', hx_trigger='change', hx_post='/controls-htmx/radio', **_htmx_tags), 'Option B'),
    ]))

  _row('select', Select(name='select', hx_trigger='change', hx_post='/controls-htmx/select', **_htmx_tags).options(['Option A', 'Option B', 'Option C'],
    placeholder='Choose...'))

  # Select-multiple inputs must be wrapped in a <form> so HTMX uses form serialization, which captures all selected values.
  # Without a form ancestor, HTMX reads input.value, which returns only the first selected option rather than iterating input.selectedOptions.
  _row('select multiple', Span(cl='flex-row gap-1ch',
    _=[Form(hx_post='/controls-htmx/select-multiple', hx_trigger='change delay:500ms', **_htmx_tags,
      _=Select(name='select_multiple', multiple='').options(['Option A', 'Option B', 'Option C'])), ftnt(2)]))

  _row('date', Input(type='date', name='date', hx_trigger='change', hx_post='/controls-htmx/date', **_htmx_tags))
  _row('time', Input(type='time', name='time', hx_trigger='change', hx_post='/controls-htmx/time', **_htmx_tags))
  _row('datetime_local', Span(cl='flex-row gap-1ch',
    _=[Input(type='datetime-local', name='datetime_local', hx_trigger='change', hx_post='/controls-htmx/datetime-local', **_htmx_tags), ftnt(3)]))
  _row('month', Span(cl='flex-row gap-1ch', _=[Input(type='month', name='month', hx_trigger='change', hx_post='/controls-htmx/month', **_htmx_tags), ftnt(3)]))
  _row('week', Span(cl='flex-row gap-1ch', _=[Input(type='week', name='week', hx_trigger='change', hx_post='/controls-htmx/week', **_htmx_tags), ftnt(3)]))


  _row('color', Input(type='color', name='color', hx_trigger='change', hx_post='/controls-htmx/color', **_htmx_tags))

  _row('range', Input(type='range', name='range', min='0', max='10', hx_trigger='input', hx_post='/controls-htmx/range', **_htmx_tags))


  # HTMX reads .value off the triggering element, except when it finds a <form> ancestor,
  # in which case it uses the JS FormData API (which handles checkboxes, files, etc. correctly).
  #
  # File inputs must be wrapped in a <form> because only FormData reads input.files (the actual
  # binary file handle); without it, HTMX falls back to input.value, which is just a fake path string.
  _row('file', Span(cl='flex-row gap-1ch',
    _=[Form(hx_encoding='multipart/form-data', hx_post='/controls-htmx/file', hx_trigger='change', **_htmx_tags,
      _=Input(type='file', name='file')), ftnt(4)]))

  div.append(Div(cl='flex-col font-small', _=['Notes:',
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

  return div
  