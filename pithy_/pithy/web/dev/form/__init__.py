# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from ....html import A, H1, Li, Main, Ul
from ...endpoint import Endpoint, NoFields
from ...request import Request
from ...response import HtmlResponse
from ..pages import dev_page


class DevFormIndex(Endpoint):
  'Index of developer form reference pages.'

  def handle_endpoint(self, request:Request, fields:NoFields) -> HtmlResponse:
    return dev_page(title='Form', breadcrumbs=[('/', 'Home'), ('/form', 'Form')],
      main=Main(H1('Form'), Ul(
        Li(A(href='/form/controls', _='Form Controls'), ': Demonstrates form controls.'))))
