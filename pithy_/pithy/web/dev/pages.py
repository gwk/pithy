# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from http import HTTPStatus

from ...html import A, H1, Html, Li, Main, Nav, Ul
from ...path import norm_path, path_dir, path_join
from ..endpoint import Endpoint
from ..request import Request
from ..response import HtmlResponse, Response
from ..static import pithy_web_static_dir_path


pithy_css_path = pithy_web_static_dir_path() + '/pithy.css'
dev_css_path = path_join(path_dir(__file__), 'dev.css')

def page_html(*, title:str, path:str, main:Main) -> HtmlResponse:
  'Return an HTML page with `main` content.'
  html = Html().doc(title=title)
  head = html.head
  head.add_stylesheet(href='/pithy.css')
  head.add_stylesheet(href='/dev.css')
  head.add_js(src='https://cdn.jsdelivr.net/npm/htmx.org@4.0.0-beta4/dist/htmx.min.js')
  body = html.body
  if path != '/':
    body.append(Nav.for_path(path))
  body.append(main)
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
    return page_html(title='Index', path='/', main=Main(H1('Index'), Ul(_=links)))


class StaticPithyCss(Endpoint):
  'The static assets.'

  def handle_request(self, request:Request) -> Response:
    assert request.path.startswith('/')
    path = norm_path(request.path)
    if not path.startswith('/'): return Response(status=HTTPStatus.NOT_FOUND)
    with open(pithy_css_path, 'r') as f:
      css = f.read()
    return Response(body=css, media_type='text/css')


class StaticDevCss(Endpoint):
  'The static assets.'

  def handle_request(self, request:Request) -> Response:
    assert request.path.startswith('/')
    path = norm_path(request.path)
    if not path.startswith('/'): return Response(status=HTTPStatus.NOT_FOUND)
    with open(dev_css_path, 'r') as f:
      css = f.read()
    return Response(body=css, media_type='text/css')
