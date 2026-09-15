# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Developer reference page demonstrating nonportable form controls.'

from ....html import Div, Form, H1, Input, Label, Main, P
from ...endpoint import Endpoint
from ...request import Request
from ...response import Response
from ..pages import dev_page
from .controls import posted_values_div


class DevFormNonportable(Endpoint):
  'Demonstrates month and week inputs.'

  methods = ('GET', 'POST')
  max_body_bytes = 64 * 1024

  class Fields:
    month: str|None
    week: str|None

  def handle_endpoint(self, request:Request, fields:Fields) -> Response:
    values = {name: val for name in ('month', 'week') if (val := getattr(fields, name)) is not None and val != ''}
    main = Main(
      H1('Nonportable Form Controls'),
      P('These controls fall back to plain text fields in desktop Safari.'
        ' Values entered in the text fallback are not validated by the browser.'),
      Div(cl='controls-demo-layout', _=[
        Form(cl='grid', method='post', _=[
          Label('month'), Input(type='month', name='month', value=fields.month or ''),
          Label('week'), Input(type='week', name='week', value=fields.week or ''),
          Label('reset'), Input(type='reset', value='Reset'),
          Label('submit'), Input(type='submit', value='Submit'),
        ]),
        posted_values_div(values),
      ]))
    return dev_page(title='Nonportable Form Controls', main=main,
      breadcrumbs=[('/', 'Home'), ('/form', 'Form'), ('/form/nonportable', 'Nonportable')])
