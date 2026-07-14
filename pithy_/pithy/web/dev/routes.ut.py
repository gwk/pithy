# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from io import BufferedReader

from pithy.web.dev.routes import routes
from pithy.web.request import Request
from pithy.web.router import Router
from utest import utest_run, utest_val


def _request(path:str) -> Request:
  return Request(method='GET', scheme='http', host='localhost', port=80,
    path=path, query_str='', headers={}, client_addr=('127.0.0.1', 0), content_length=None)


def _content_type(router:Router, path:str) -> object:
  request = _request(path)
  response = router.resolve_handler(request).handle_request(request)
  if isinstance(response.body, BufferedReader): response.body.close()
  return response.headers.get('content-type')


@utest_run
def _() -> None:
  'pithy.web.dev: bundled and dev static assets are served through FilesHandler mounts.'
  router = Router(routes)

  utest_val('text/css;charset=utf-8', _content_type(router, '/static/pithy/pithy.css'), desc='pithy.css served as css')
  utest_val('text/css;charset=utf-8', _content_type(router, '/static/dev/dev.css'), desc='dev.css served as css')
