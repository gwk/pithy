# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import asyncio
from collections.abc import Mapping

from pithy.web.endpoint import Endpoint
from pithy.web.request import Request as PithyRequest
from pithy.web.response import Response as PithyResponse
from pithy.web.starlette import endpoint_adapter, endpoint_route
from starlette.authentication import AuthCredentials
from starlette.exceptions import HTTPException
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse
from utest import utest_run, utest_val


def _run(endpoint_cls:type[Endpoint], *, method:str='GET', path:str='/', query:str='', headers:Mapping[str,str]|None=None,
 body:bytes=b'', path_params:Mapping[str,object]|None=None, scope_extra:Mapping[str,object]|None=None,
 privileges:tuple[str,...]=()) -> StarletteResponse:
  'Drive the adapter with a hand-built ASGI request and return the resulting Starlette Response.'
  raw_headers = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
  scope:dict[str,object] = {
    'type': 'http',
    'http_version': '1.1',
    'method': method,
    'scheme': 'http',
    'path': path,
    'raw_path': path.encode(),
    'query_string': query.encode(),
    'headers': raw_headers,
    'client': ('127.0.0.1', 12345),
    'server': ('localhost', 80),
    'path_params': dict(path_params or {}),
  }
  if scope_extra: scope.update(scope_extra)

  async def receive() -> dict[str,object]:
    return {'type': 'http.request', 'body': body, 'more_body': False}

  s_request = StarletteRequest(scope, receive)
  adapted = endpoint_adapter(endpoint_cls, privileges=privileges)

  async def _call() -> StarletteResponse:
    return await adapted(s_request)

  return asyncio.run(_call())


class HelloEndpoint(Endpoint):
  class Fields:
    name:str
  fields:Fields
  def handle_request(self, request:PithyRequest) -> PithyResponse:
    return PithyResponse(body=f'hello {self.fields.name}')


class ItemEndpoint(Endpoint):
  class Fields:
    id:int
  fields:Fields
  def handle_request(self, request:PithyRequest) -> PithyResponse:
    return PithyResponse(body=f'id={self.fields.id}')


class FormEndpoint(Endpoint):
  methods = 'POST'
  max_body_bytes = 1024
  class Fields:
    name:str
  fields:Fields
  def handle_request(self, request:PithyRequest) -> PithyResponse:
    return PithyResponse(body=self.fields.name)


class JsonEndpoint(Endpoint):
  methods = 'POST'
  max_body_bytes = 1024
  class Fields:
    name:str
  fields:Fields
  def handle_request(self, request:PithyRequest) -> PithyResponse:
    return PithyResponse(body=self.fields.name)


class CtxEndpoint(Endpoint):
  def handle_request(self, request:PithyRequest) -> PithyResponse:
    return PithyResponse(body=f"{request.ctx.get('user')}|{request.ctx.get('session')}")


class PrivilegedEndpoint(Endpoint):
  def handle_request(self, request:PithyRequest) -> PithyResponse:
    return PithyResponse(body='ok')


@utest_run
def _() -> None:
  'Adapter: GET with a query param fills fields and returns the body.'
  resp = _run(HelloEndpoint, query='name=alice')
  utest_val(200, resp.status_code)
  utest_val(b'hello alice', resp.body)


@utest_run
def _() -> None:
  'Adapter: path params already typed by Starlette pass through pithy conversion.'
  resp = _run(ItemEndpoint, path='/items/7', path_params={'id': 7})
  utest_val(b'id=7', resp.body)


@utest_run
def _() -> None:
  'Adapter: urlencoded POST body is parsed by pithy.'
  resp = _run(FormEndpoint, method='POST',
    headers={'content-type': 'application/x-www-form-urlencoded', 'content-length': '10'}, body=b'name=bobby')
  utest_val(200, resp.status_code)
  utest_val(b'bobby', resp.body)


@utest_run
def _() -> None:
  'Adapter: JSON POST body is parsed by pithy.'
  body = b'{"name":"carol"}'
  resp = _run(JsonEndpoint, method='POST',
    headers={'content-type': 'application/json', 'content-length': str(len(body))}, body=body)
  utest_val(b'carol', resp.body)


@utest_run
def _() -> None:
  'Adapter: an unknown query param yields a 400 (pithy app-level validation is preserved).'
  resp = _run(HelloEndpoint, query='name=alice&bogus=1')
  utest_val(400, resp.status_code)


@utest_run
def _() -> None:
  'Adapter: a declared body over max_body_bytes yields 413 before the body is read.'
  resp = _run(FormEndpoint, method='POST',
    headers={'content-type': 'application/x-www-form-urlencoded', 'content-length': '5000'}, body=b'name=x')
  utest_val(413, resp.status_code)


@utest_run
def _() -> None:
  'Adapter: ctx is populated from the ASGI scope (user, session).'
  resp = _run(CtxEndpoint, scope_extra={'user': 'dave', 'session': {'uid': 7}})
  utest_val(b"dave|{'uid': 7}", resp.body)


@utest_run
def _() -> None:
  'endpoint_route: methods come from the Endpoint and the route is named for the Endpoint class.'
  route = endpoint_route('/x', FormEndpoint, privileges=())
  utest_val(['POST'], sorted(route.methods or ()))
  utest_val('FormEndpoint', route.name)


@utest_run
def _() -> None:
  'endpoint_route: field converters are resolved when the route is built, not on the first request.'
  class RouteResolvedEndpoint(Endpoint):
    class Fields:
      n:int
    fields:Fields
    def handle_request(self, request:PithyRequest) -> PithyResponse:
      return PithyResponse(body=f'{self.fields.n}')
  utest_val(False, RouteResolvedEndpoint._converters_resolved)
  endpoint_route('/n', RouteResolvedEndpoint, privileges=())
  utest_val(True, RouteResolvedEndpoint._converters_resolved)


@utest_run
def _() -> None:
  'Adapter: privileges held by the request scopes returns the endpoint response.'
  resp = _run(PrivilegedEndpoint, privileges=('Staff',), scope_extra={'auth': AuthCredentials(['Staff'])})
  utest_val(200, resp.status_code)
  utest_val(b'ok', resp.body)


@utest_run
def _() -> None:
  'Adapter: a missing required privilege raises HTTPException(403) for the host app to convert (e.g. signin redirect).'
  try:
    _run(PrivilegedEndpoint, privileges=('Staff',), scope_extra={'auth': AuthCredentials([])})
  except HTTPException as e:
    utest_val(403, e.status_code)
  else:
    raise AssertionError('expected HTTPException')


@utest_run
def _() -> None:
  'Adapter: empty privileges declares a public endpoint, which needs no auth scope in the request.'
  resp = _run(HelloEndpoint, query='name=eve', privileges=())
  utest_val(200, resp.status_code)
  utest_val(b'hello eve', resp.body)
