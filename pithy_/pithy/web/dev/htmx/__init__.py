# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from ....html import A, H1, Li, Main, Ul
from ...endpoint import Endpoint, NoFields
from ...request import Request
from ...response import HtmlResponse
from ..pages import dev_page


class DevHtmxIndex(Endpoint):
  'Index of HTMX developer demos.'

  def handle_endpoint(self, request:Request, fields:NoFields) -> HtmlResponse:
    return dev_page(title='HTMX', breadcrumbs=[('/', 'Home'), ('/htmx', 'HTMX')],
      main=Main(H1('HTMX'), Ul(
        Li(A(href='/htmx/controls', _='HTMX Controls'), ': Standard HTML form controls using HTMX.'))))
