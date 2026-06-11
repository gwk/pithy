# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from ...html import A, H1, Html, Li, Main, Ul
from ..endpoint import Endpoint
from ..request import Request
from ..response import HtmlResponse, Response
from ..static import pithy_web_static_dir_path


pithy_css_path = pithy_web_static_dir_path() + '/pithy.css'


def page_html(*, title:str, main:Main) -> HtmlResponse:
  'Return an HTML page with `main` content.'
  html = Html().doc(title=title)
  head = html.head
  head.add_stylesheet(href='/pithy.css')
  head.add_js(src='https://cdn.jsdelivr.net/npm/htmx.org@4.0.0-beta1/dist/htmx.min.js')
  html.append(main)
  return HtmlResponse(body=html)


class IndexHtml(Endpoint):
  'The pithy.web.dev index page.'

  def handle_request(self, request:Request) -> HtmlResponse:
    from .routes import routes
    links = []
    for path, endpoint in routes.items():
      if path == '/' or path.endswith('.htmx'): continue
      text = ''
      if doc := endpoint.__doc__:
        text = ': ' + doc
      links.append(Li(A(href=path, _=path), text))
    return page_html(title='Index', main=Main(H1('Index'), Ul(_=links)))


class PithyCss(Endpoint):
  'The pithy.css stylesheet.'

  def handle_request(self, request:Request) -> Response:
    with open(pithy_css_path, 'r') as f:
      css = f.read()
    return Response(body=css, media_type='text/css')
