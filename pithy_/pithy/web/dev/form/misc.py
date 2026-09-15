# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Developer reference page demonstrating miscellaneous buttons.'

from urllib.parse import quote

from ....html import Button, Div, Form, H1, Input, Label, Main, P, Span
from ...endpoint import Endpoint
from ...request import Request
from ...response import Response
from ..pages import dev_page
from .controls import posted_values_div


image_button_svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="64" height="32" viewBox="0 0 64 32">
  <rect width="64" height="32" rx="3" fill="black"/>
  <path d="M8 16h48M32 4v24" fill="none" stroke="#39ff14" stroke-width="2"/>
</svg>'''
image_button_src = f'data:image/svg+xml,{quote(image_button_svg)}'


class DevFormMisc(Endpoint):
  'Demonstrates a native popover button and an image submit button.'

  methods = ('GET', 'POST')
  max_body_bytes = 64 * 1024

  class Fields:
    x: str|None
    y: str|None

  def handle_endpoint(self, request:Request, fields:Fields) -> Response:
    values = {name: val for name in ('x', 'y') if (val := getattr(fields, name)) is not None}
    main = Main(
      H1('Miscellaneous Buttons'),
      Div(cl='controls-demo-layout', _=[
        Div(
          Div(cl='form_grid', _=[
            Label('button'),
            Input(type='button', value='Toggle popover', popovertarget='example-popover'),
          ]),
          Div(id='example-popover', cl='controls-demo-popover panel flow', popover='', _=[
            P('This popover uses native HTML without JavaScript.'),
            Button(type='button', popovertarget='example-popover', popovertargetaction='hide', _='Close'),
          ]),
          Form(cl='grid', method='post', _=[
            Label('image'),
            Span(cl='flex-row gap-1ch align-items-center', _=[
              Input(type='image', src=image_button_src, alt='Submit with image'),
              Span(cl='font-small', _='(Submits click coordinates)'),
            ]),
          ]),
        ),
        posted_values_div(values),
      ]))
    return dev_page(title='Miscellaneous Buttons', main=main,
      breadcrumbs=[('/', 'Home'), ('/form', 'Form'), ('/form/misc', 'Miscellaneous')])
