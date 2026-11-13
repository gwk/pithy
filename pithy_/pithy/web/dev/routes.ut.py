# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.web.dev.charts import chart_kinds
from pithy.web.dev.routes import routes
from pithy.web.dev.tests import fixture_pages
from pithy.web.request import Request
from pithy.web.response import close_response_body
from pithy.web.router import Router
from utest import utest, utest_run


def _request(path:str) -> Request:
  return Request(method='GET', scheme='http', host='localhost', port=80,
    raw_path=path, query_str='', headers={}, client_addr=('127.0.0.1', 0), content_length=None)


def _content_type(router:Router, path:str) -> object:
  request = _request(path)
  response = router.resolve_route(request).get_handler(request).handle_request(request)
  close_response_body(response.body)
  return response.headers.get('content-type')


@utest_run
def _() -> None:
  'pithy.web.dev: bundled and dev static assets are served through FilesHandler mounts.'
  router = Router(routes, default_public=True)

  utest('text/css;charset=utf-8', _content_type, router, '/static/pithy/pithy.css',
    _utest_label=repr('pithy.css served as css'))
  utest('text/css;charset=utf-8', _content_type, router, '/static/dev/dev.css', _utest_label=repr('dev.css served as css'))
  utest('font/woff2', _content_type, router, '/static/pithy/fonts/NotoEmoji-VariableFont_wght.woff2',
    _utest_label=repr('bundled Noto Emoji served as a font without a text charset'))


@utest_run
def _() -> None:
  'pithy.web.dev: every fixture page listed on the tests page is served as html.'
  router = Router(routes, default_public=True)
  for path, name, _desc in fixture_pages:
    utest('text/html;charset=utf-8', _content_type, router, path, _utest_label=repr(name))


@utest_run
def _() -> None:
  'pithy.web.dev: the chart index and every listed chart kind page render as html.'
  router = Router(routes, default_public=True)
  for path in ('/charts', *(path for path, _label, _desc in chart_kinds)):
    utest('text/html;charset=utf-8', _content_type, router, path, _utest_label=repr(path))
