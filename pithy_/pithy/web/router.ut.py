# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Mapping

from pithy.web.endpoint import Endpoint, GetHandler
from pithy.web.errors import MethodNotAllowedError
from pithy.web.handler import RoutableHandler
from pithy.web.request import Request
from pithy.web.response import Response
from pithy.web.router import Router, RouterApp, RouteTarget
from utest import utest, utest_exc, utest_run, utest_val


# Test endpoints.

class EpHome(Endpoint):
  def get(self, request:Request, fields:None) -> Response:
    return Response(body='home')

class EpAbout(Endpoint):
  def get(self, request:Request, fields:None) -> Response:
    return Response(body='about')

class EpUser(Endpoint):
  class Get:
    id:int
  def get(self, request:Request, fields:Get) -> Response:
    return Response(body=f'user:{fields.id}')

class EpStatic(Endpoint):
  class Get:
    p:str
  def get(self, request:Request, fields:Get) -> Response:
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


@utest_run
def _() -> None:
  'Router: accepts a mix of Endpoint classes, other handler classes and functions, adapting functions at registration.'
  def user(request:Request, id:int, *, note:str|None) -> Response:
    return Response(body=f'{request.method}:{id}:{note!r}')

  # The same function may be registered for several routes.
  routes:Mapping[str,RouteTarget] = {
    '/': EpHome, '/users/{id:int}': user, '/members/{id:int}': user, '/static/{subpath:path}': HandlerFiles}
  app = RouterApp(routes)
  match = app.router.endpoint_for_path('/users/7')
  assert match is not None
  handler_cls, params = match
  utest_val(True, issubclass(handler_cls, Endpoint))
  utest_val({'id': 7}, params)

  def dispatch(method:str, path:str, query_str:str='') -> bytes|bytearray|None:
    request = Request(method=method, scheme='http', host='localhost', port=80,
      path=path, query_str=query_str, headers={}, client_addr=('127.0.0.1', 0), content_length=None)
    handler = app.resolve_handler(request)
    handler.prepare(request)
    body = handler.handle_request(request).body
    assert body is None or isinstance(body, (bytes, bytearray))
    return body

  utest(b"GET:7:'hi'", dispatch, 'GET', '/users/7', 'note=hi')
  utest(b'HEAD:8:None', dispatch, 'HEAD', '/members/8')
  utest(b'home', dispatch, 'GET', '/')
  utest(b'files:a.css', dispatch, 'GET', '/static/a.css')

  # Mapping covariance: class-only and function-only dictionaries typecheck as routes.
  class_routes:dict[str,type[RoutableHandler]] = {'/': EpHome}
  function_routes:dict[str,GetHandler] = {'/users/{id:int}': user}
  Router(class_routes)
  RouterApp(function_routes)


@utest_run
def _() -> None:
  'Router: validates route targets during registration and names the route in function declaration errors.'
  class Left: pass
  class Right: pass
  def default(request:Request, count:int=1) -> Response:
    return Response()
  def unsupported(request:Request, value:Left|Right) -> Response:
    return Response()
  utest_exc(TypeError(f"Route '/d': {default.__qualname__} parameters must not have defaults; "
    'use optional field types for missing values.'), Router, {'/d': default})
  # The converters of adapted functions are resolved at registration.
  utest_exc(TypeError(f'{unsupported.__qualname__}.Get.value: no converter is available for field type {Left|Right!r}.'),
    Router, {'/': unsupported})
  utest_exc(TypeError("Route '/': handler class must derive from RoutableHandler."), Router, {'/': object})
