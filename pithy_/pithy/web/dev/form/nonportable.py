# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Developer reference page demonstrating nonportable form controls.'

from ....html import Div, Form, H1, Input, Label, Main, P
from ...endpoint import Endpoint, NoFields
from ...request import Request
from ...response import Response
from ..pages import dev_page
from .controls import posted_values_div


class DevFormNonportable(Endpoint):
  'Demonstrates month and week inputs.'

  max_body_bytes = 64 * 1024

  class Post:
    month:str
    week:str

  def get(self, request:Request, fields:NoFields) -> Response:
    return nonportable_page(month='', week='')

  def post(self, request:Request, fields:Post) -> Response:
    return nonportable_page(month=fields.month, week=fields.week)


def nonportable_page(*, month:str, week:str) -> Response:
  values:dict[str,str|list[str]] = {name: val for name, val in (('month', month), ('week', week)) if val != ''}
  main = Main(
    H1('Nonportable Form Controls'),
    P('These controls fall back to plain text fields in desktop Safari.'
      ' Values entered in the text fallback are not validated by the browser.'),
    Div(cl='controls-demo-layout', _=[
      Form(cl='grid', method='post', _=[
        Label('month'), Input(type='month', name='month', value=month),
        Label('week'), Input(type='week', name='week', value=week),
        Label('reset'), Input(type='reset', value='Reset'),
        Label('submit'), Input(type='submit', value='Submit'),
      ]),
      posted_values_div(values),
    ]))
  return dev_page(title='Nonportable Form Controls', main=main,
    breadcrumbs=[('/', 'Home'), ('/form', 'Form'), ('/form/nonportable', 'Nonportable')])
