# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Iterable

from ...html import A, H1, Html, Li, Main, Nav, Ul
from ...path import path_dir, path_join
from ..endpoint import Endpoint, NoFields
from ..files import FilesHandler
from ..request import Request
from ..response import HtmlResponse
from ..static import pithy_web_static_dir_path


def page_html(*, title:str, breadcrumbs:Iterable[tuple[str,str]]=(), main:Main) -> HtmlResponse:
  'Return an HTML page with `main` content.'
  html = Html().doc(title=title)
  head = html.head
  head.add_stylesheet(href='/static/pithy/pithy.css')
  head.add_stylesheet(href='/static/dev/dev.css')
  head.add_js(src='https://cdn.jsdelivr.net/npm/htmx.org@4.0.0-beta4/dist/htmx.min.js')
  body = html.body
  if breadcrumbs:
    body.append(Nav.breadcrumbs(breadcrumbs))
  body.append(main)
  return HtmlResponse(body=html)


class IndexHtml(Endpoint):
  'The pithy.web.dev index page.'

  def handle_endpoint(self, request:Request, fields:NoFields) -> HtmlResponse:
    from .routes import routes
    links = []
    for path, endpoint in routes.items():
      if path == '/' or path.endswith('.htmx') or '{' in path: continue # Skip the index itself, htmx fragments, and mounts.
      text = ''
      if doc := endpoint.__doc__:
        text = ': ' + doc
      links.append(Li(A(href=path, _=path), text))
    return page_html(title='Index', main=Main(H1('Index'), Ul(_=links)))


class PithyStaticFiles(FilesHandler):
  'Static assets bundled with pithy.web.'
  local_dir = pithy_web_static_dir_path()


class DevStaticFiles(FilesHandler):
  'Static assets for the pithy.web.dev demo app.'
  local_dir = path_join(path_dir(__file__), 'static')
