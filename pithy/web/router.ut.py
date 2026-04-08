# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.web.endpoint import Endpoint
from pithy.web.request import Request
from pithy.web.response import Response
from pithy.web.router import Router
from utest import utest, utest_run


# Test endpoints.

class EpHome(Endpoint):
  def handle(self, request:Request) -> Response:
    return Response(body='home')

class EpAbout(Endpoint):
  def handle(self, request:Request) -> Response:
    return Response(body='about')

class EpUser(Endpoint):
  def handle(self, request:Request) -> Response:
    return Response(body=f'user:{request.path_params}')

class EpStatic(Endpoint):
  def handle(self, request:Request) -> Response:
    return Response(body=f'files:{request.path_params}')


ep_home = EpHome()
ep_about = EpAbout()
ep_user = EpUser()
ep_static = EpStatic()


@utest_run
def _() -> None:
  'Router: dispatches fixed and pattern routes.'
  router = Router({
    '/': ep_home,
    '/about': ep_about,
    '/users/{id:int}': ep_user,
    '/static/{p:path}': ep_static,
  })

  utest((ep_home, {}), router.endpoint_for_path, '/')
  utest((ep_about, {}), router.endpoint_for_path, '/about')
  utest((ep_user, {'id': 7}), router.endpoint_for_path, '/users/7')
  utest((ep_static, {'p': 'dir/file.txt'}), router.endpoint_for_path, '/static/dir/file.txt')
  utest(None, router.endpoint_for_path, '/missing')


@utest_run
def _() -> None:
  'Router: dispatch calls endpoint.handle and sets path_params on request.'
  router = Router({
    '/': ep_home,
    '/users/{id:int}': ep_user,
  })

  def dispatch_body(path:str) -> str|None:
    result = router.endpoint_for_path(path)
    if result is None: return None
    endpoint, path_params = result
    request = Request(method='GET', scheme='http', host='localhost', port=80,
      path=path, query='', headers={}, client_addr=('127.0.0.1', 0), content_length=None)
    request.path_params = path_params
    response = endpoint.handle(request)
    return response.body.decode() if isinstance(response.body, (bytes, bytearray)) else None

  utest('home', dispatch_body, '/')
  utest("user:{'id': 7}", dispatch_body, '/users/7')
  utest(None, dispatch_body, '/missing')
