# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from ....html import A, H1, Li, Main, Ul
from ...endpoint import Endpoint
from ...request import Request
from ...response import HtmlResponse
from ..pages import page_html


class DevControlsIndex(Endpoint):
  'Index of developer control reference pages.'

  def handle_request(self, request:Request) -> HtmlResponse:
    from ..routes import routes
    links = []
    for path, endpoint in routes.items():
      if not path.startswith('/controls/') or path.endswith('.htmx'): continue
      text = (': ' + endpoint.__doc__) if endpoint.__doc__ else ''
      links.append(Li(A(href=path, _=path), text))

    return page_html(title='Controls', breadcrumbs=[('/', 'Home'), ('/controls', 'Controls')],
      main=Main(H1('Controls'), Ul(_=links)))
