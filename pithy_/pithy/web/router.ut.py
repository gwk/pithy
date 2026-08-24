# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Mapping

from pithy.web.endpoint import Endpoint, NoFields
from pithy.web.errors import MethodNotAllowedError
from pithy.web.handler import RoutableHandler
from pithy.web.request import Request
from pithy.web.response import Response
from pithy.web.router import Router
from utest import utest, utest_exc, utest_run


# Test endpoints.

class EpHome(Endpoint):
  def handle_endpoint(self, request:Request, fields:NoFields) -> Response:
    return Response(body='home')

class EpAbout(Endpoint):
  def handle_endpoint(self, request:Request, fields:NoFields) -> Response:
    return Response(body='about')

class EpUser(Endpoint):
  class Fields:
    id:int
  def handle_endpoint(self, request:Request, fields:Fields) -> Response:
    return Response(body=f'user:{fields.id}')

class EpStatic(Endpoint):
  class Fields:
    p:str
  def handle_endpoint(self, request:Request, fields:Fields) -> Response:
    return Response(body=f'files:{fields.p}')


class HandlerFiles(RoutableHandler):
  'A minimal non-Endpoint route target, standing in for the coming FilesHandler.'
  _methods = frozenset({'GET', 'HEAD'})
  def __init__(self, request:Request, path_params:Mapping[str,object]) -> None:
    self.subpath = path_params.get('subpath', '')
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'files:{self.subpath}')


@utest_run
def _() -> None:
  'Router: dispatches fixed and pattern routes.'
  router = Router({
    '/': EpHome,
    '/about': EpAbout,
    '/users/{id:int}': EpUser,
    '/static/{p:path}': EpStatic,
  })

  utest((EpHome, {}), router.endpoint_for_path, '/')
  utest((EpAbout, {}), router.endpoint_for_path, '/about')
  utest((EpUser, {'id': 7}), router.endpoint_for_path, '/users/7')
  utest((EpStatic, {'p': 'dir/file.txt'}), router.endpoint_for_path, '/static/dir/file.txt')
  utest(None, router.endpoint_for_path, '/missing')


@utest_run
def _() -> None:
  'Router: resolve_handler dispatches and handles requests.'
  router = Router({
    '/': EpHome,
    '/users/{id:int}': EpUser,
  })

  def dispatch_body(path:str) -> str|None:
    request = Request(method='GET', scheme='http', host='localhost', port=80,
      path=path, query_str='', headers={}, client_addr=('127.0.0.1', 0), content_length=None)
    try:
      handler = router.resolve_handler(request)
    except Exception:
      return None
    response = handler.handle_request(request)
    return response.body.decode() if isinstance(response.body, (bytes, bytearray)) else None

  utest('home', dispatch_body, '/')
  utest('user:7', dispatch_body, '/users/7')
  utest(None, dispatch_body, '/missing')


@utest_run
def _() -> None:
  'Router: dispatches to a non-Endpoint RoutableHandler and enforces its _methods.'
  router = Router({
    '/': EpHome,
    '/static/{subpath:path}': HandlerFiles,
  })

  def dispatch(method:str, path:str) -> str|None:
    request = Request(method=method, scheme='http', host='localhost', port=80,
      path=path, query_str='', headers={}, client_addr=('127.0.0.1', 0), content_length=None)
    try:
      handler = router.resolve_handler(request)
    except MethodNotAllowedError:
      return 'method-not-allowed'
    except Exception:
      return None
    response = handler.handle_request(request)
    return response.body.decode() if isinstance(response.body, (bytes, bytearray)) else None

  utest('files:css/app.css', dispatch, 'GET', '/static/css/app.css')
  utest('method-not-allowed', dispatch, 'POST', '/static/css/app.css')
  utest('home', dispatch, 'GET', '/')


@utest_run
def _() -> None:
  'Router: overlapping route patterns are rejected at construction (mounts get shadow-checking for free).'
  utest_exc(ValueError, Router, {'/x/{a:path}': EpHome, '/x/{b:path}': EpAbout})
