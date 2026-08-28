# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Iterable, Sequence

from ...html import A, Footer, H1, H2, Header, Html, Li, Main, Nav, P, Script, Ul
from ...path import path_dir, path_join
from ..endpoint import Endpoint, NoFields
from ..files import FilesHandler
from ..request import Request
from ..response import HtmlResponse
from ..static import pithy_web_static_dir_path


site_name = 'pithy.web.dev'

common_css_paths = (
  '/static/pithy/pithy.css',
  '/static/pithy/htmx.css',
  '/static/dev/dev.css',
)

htmx_src = 'https://cdn.jsdelivr.net/npm/htmx.org@4.0.0-beta4/dist/htmx.min.js'

# The site navigation bar. Each entry is a (path, label) pair.
nav_links = (
  ('/', 'Home'),
  ('/typography', 'Typography'),
  ('/tables', 'Tables'),
  ('/controls/form', 'Form'),
  ('/controls/htmx', 'HTMX'),
)


def dev_page(*, title:str, main:Main, breadcrumbs:Iterable[tuple[str,str]]=(),
 css_paths:Sequence[str]=()) -> HtmlResponse:
  '''
  Return the complete page for `main`, wrapped in the dev app's shell.

  This is the single entry point through which every dev endpoint renders a page,
  so that the shell (head, header, nav, footer) is defined in exactly one place.
  '''
  html = Html.doc(title=f'{site_name}: {title}')

  head = html.head
  head.add_meta(name='viewport', content='width=device-width, initial-scale=1.0')
  for css_path in (*common_css_paths, *css_paths):
    head.add_stylesheet(href=css_path)
  # pithy.js must not be deferred: it defines `once()`, which inline script elements call as they are parsed.
  head.append(Script(src='/static/pithy/pithy.js'))
  head.append(Script(src='/static/dev/dev.js'))
  head.add_js(src=htmx_src)

  body = html.body
  body.append(Header(site_name))
  body.append(Nav(cl='navbar', _=[A(href=p, _=label) for p, label in nav_links]))
  if trail := list(breadcrumbs):
    *ancestors, (_, current) = trail
    main.prepend(Nav.breadcrumbs(ancestors, current=current))
  body.append(main)
  body.append(Footer('Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.'))

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
    main = Main(
      H1(site_name),
      P('A reference demo of the pithy.web stack.'),
      H2('Pages'),
      Ul(_=links))
    return dev_page(title='Index', main=main)


class PithyStaticFiles(FilesHandler):
  'Static assets bundled with pithy.web.'
  local_dir = pithy_web_static_dir_path()


class DevStaticFiles(FilesHandler):
  'Static assets for the pithy.web.dev demo app.'
  local_dir = path_join(path_dir(__file__), 'static')
