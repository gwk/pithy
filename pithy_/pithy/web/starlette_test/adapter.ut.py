# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import asyncio
from collections.abc import Mapping
from io import BufferedReader
from tempfile import TemporaryDirectory

from pithy.web.auth import allow_public, requires_authenticated, requires_privileges
from pithy.web.endpoint import Endpoint
from pithy.web.request import Request as PithyRequest
from pithy.web.response import Response as PithyResponse
from pithy.web.starlette import _raw_path_from_scope, convert_response, endpoint_adapter, endpoint_route
from starlette.authentication import AuthCredentials, SimpleUser, UnauthenticatedUser
from starlette.exceptions import HTTPException
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse, StreamingResponse
from starlette.types import Message, Scope
from utest import utest_exc, utest_run, utest_val


def _run(endpoint_cls:type[Endpoint], *, method:str='GET', path:str='/', query:str='', headers:Mapping[str,str]|None=None,
 body:bytes=b'', path_params:Mapping[str,object]|None=None, scope_extra:Mapping[str,object]|None=None) -> StarletteResponse:
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
  adapted = endpoint_adapter(endpoint_cls)

  async def _call() -> StarletteResponse:
    return await adapted(s_request)

  return asyncio.run(_call())


@allow_public
class HelloEndpoint(Endpoint):
  class Get:
    name:str
  def get(self, request:PithyRequest, fields:Get) -> PithyResponse:
    return PithyResponse(body=f'hello {fields.name}')


@allow_public
class ItemEndpoint(Endpoint):
  class Get:
    id:int
  def get(self, request:PithyRequest, fields:Get) -> PithyResponse:
    return PithyResponse(body=f'id={fields.id}')


@allow_public
class PathEndpoint(Endpoint):
  class Get: pass
  def get(self, request:PithyRequest, fields:Get) -> PithyResponse:
    return PithyResponse(body=f'{request.raw_path}|{request.path}')


@allow_public
class FormEndpoint(Endpoint):
  max_body_bytes = 1024
  class Post:
    name:str
  def post(self, request:PithyRequest, fields:Post) -> PithyResponse:
    return PithyResponse(body=fields.name)


@allow_public
class JsonEndpoint(Endpoint):
  max_body_bytes = 1024
  class Post:
    name:str
  def post(self, request:PithyRequest, fields:Post) -> PithyResponse:
    return PithyResponse(body=fields.name)


@allow_public
class CtxEndpoint(Endpoint):
  def get(self, request:PithyRequest, fields:None) -> PithyResponse:
    return PithyResponse(body=f"{request.ctx['user'].display_name}|{request.ctx.get('session')}")


@requires_privileges('Staff')
class PrivilegedEndpoint(Endpoint):
  def get(self, request:PithyRequest, fields:None) -> PithyResponse:
    return PithyResponse(body='ok')


@utest_run
def _() -> None:
  'File responses stream in chunks and close the file after sending.'
  with TemporaryDirectory() as tmp:
    path = f'{tmp}/body'
    content = b'x' * (64 * 1024 + 3)
    with open(path, 'wb') as writer: writer.write(content)
    file = open(path, 'rb')
    assert isinstance(file, BufferedReader)
    response = convert_response(PithyResponse(body=file))
    utest_val(True, isinstance(response, StreamingResponse))
    utest_val(False, file.closed)
    utest_val((b'content-length', str(len(content)).encode()), response.raw_headers[0])

    messages:list[Message] = []
    async def receive() -> Message: raise AssertionError('receive should not be called')
    async def send(message:Message) -> None: messages.append(message)
    scope:Scope = {'type':'http', 'asgi':{'spec_version':'2.4'}}
    asyncio.run(response(scope, receive, send))
    utest_val(content, b''.join(message.get('body', b'') for message in messages[1:]))
    utest_val([64 * 1024, 3, 0], [len(message.get('body', b'')) for message in messages[1:]])
    utest_val(True, file.closed)


@utest_run
def _() -> None:
  'HEAD preserves the file length header but closes the file without streaming it.'
  with TemporaryDirectory() as tmp:
    path = f'{tmp}/body'
    with open(path, 'wb') as writer: writer.write(b'abc')
    file = open(path, 'rb')
    response = convert_response(PithyResponse(body=file), method='HEAD')
    utest_val(b'', response.body)
    utest_val((b'content-length', b'3'), response.raw_headers[0])
    utest_val(True, file.closed)


@utest_run
def _() -> None:
  'A send failure closes a streamed file response.'
  with TemporaryDirectory() as tmp:
    path = f'{tmp}/body'
    with open(path, 'wb') as writer: writer.write(b'abc')
    file = open(path, 'rb')
    response = convert_response(PithyResponse(body=file))
    async def receive() -> Message: raise AssertionError('receive should not be called')
    async def send(message:Message) -> None: raise RuntimeError('send failed')
    scope:Scope = {'type':'http', 'asgi':{'spec_version':'2.4'}}
    try: asyncio.run(response(scope, receive, send))
    except RuntimeError as exc: utest_val('send failed', str(exc))
    else: raise AssertionError('expected send failure')
    utest_val(True, file.closed)


@utest_run
def _() -> None:
  'Adapter: GET with a query param fills fields and returns the body.'
  resp = _run(HelloEndpoint, query='name=alice')
  utest_val(200, resp.status_code)
  utest_val(b'hello alice', resp.body)


@utest_run
def _() -> None:
  'Adapter: HEAD omits the body and preserves its content length.'
  resp = _run(HelloEndpoint, method='HEAD', query='name=alice')
  utest_val(b'', resp.body)
  utest_val('11', resp.headers['content-length'])


@utest_run
def _() -> None:
  'Adapter: path params already typed by Starlette pass through pithy conversion.'
  resp = _run(ItemEndpoint, path='/items/7', path_params={'id': 7})
  utest_val(b'id=7', resp.body)


@utest_run
def _() -> None:
  'Adapter: raw_path is the wire form from the ASGI scope, not the path that Starlette decoded.'
  resp = _run(PathEndpoint, path='/a b/100%', scope_extra={'raw_path': b'/a%20b/100%25'})
  utest_val(b'/a%20b/100%25|/a b/100%25', resp.body)


@utest_run
def _() -> None:
  'Adapter: without a scope raw_path, the decoded path is re-quoted.'
  utest_val('/a%20b/caf%C3%A9', _raw_path_from_scope({'type': 'http'}, '/a b/caf\u00e9'))
  utest_val('/a%20b', _raw_path_from_scope({'type': 'http', 'raw_path': b'/a%20b'}, '/ignored'))


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
  resp = _run(CtxEndpoint, scope_extra={'user': SimpleUser('dave'), 'session': {'uid': 7}})
  utest_val(b"dave|{'uid': 7}", resp.body)


@utest_run
def _() -> None:
  'endpoint_route: methods come from the Endpoint and the route is named for the Endpoint class.'
  route = endpoint_route('/x', FormEndpoint)
  utest_val(['POST'], sorted(route.methods or ()))
  utest_val('FormEndpoint', route.name)


@utest_run
def _() -> None:
  'endpoint_route: field converters are resolved when the route is built, not on the first request.'
  @allow_public
  class RouteResolvedEndpoint(Endpoint):
    class Get:
      n:int
    def get(self, request:PithyRequest, fields:Get) -> PithyResponse:
      return PithyResponse(body=f'{fields.n}')
  utest_val(False, RouteResolvedEndpoint._converters_resolved)
  endpoint_route('/n', RouteResolvedEndpoint)
  utest_val(True, RouteResolvedEndpoint._converters_resolved)


@utest_run
def _() -> None:
  'Adapter: privileges held by the request scopes returns the endpoint response.'
  resp = _run(PrivilegedEndpoint, scope_extra={'user': SimpleUser('dave'), 'auth': AuthCredentials(['Staff'])})
  utest_val(200, resp.status_code)
  utest_val(b'ok', resp.body)


@utest_run
def _() -> None:
  'Adapter: a missing required privilege raises HTTPException(403) for the host app to convert (e.g. signin redirect).'
  try:
    _run(PrivilegedEndpoint, scope_extra={'auth': AuthCredentials([])})
  except HTTPException as e:
    utest_val(403, e.status_code)
  else:
    raise AssertionError('expected HTTPException')


@utest_run
def _() -> None:
  'Adapter: a public endpoint needs no auth scope in the request.'
  resp = _run(HelloEndpoint, query='name=eve')
  utest_val(200, resp.status_code)
  utest_val(b'hello eve', resp.body)


@utest_run
def _() -> None:
  'Adapter: restricted adapters wrap access checks, and every declared scope is required.'
  class Methods(Endpoint):
    max_body_bytes = 16
    @requires_privileges('Staff', 'Editor')
    def get(self, request:PithyRequest, fields:None) -> PithyResponse: return PithyResponse(body='get')
    @requires_privileges('Editor', 'Staff')
    def post(self, request:PithyRequest, fields:None) -> PithyResponse: return PithyResponse(body='post')

  utest_val(True, hasattr(endpoint_adapter(Methods), '__wrapped__'))
  utest_val(True, hasattr(endpoint_adapter(PrivilegedEndpoint), '__wrapped__'))
  utest_val(False, hasattr(endpoint_adapter(HelloEndpoint), '__wrapped__'))
  resp = _run(Methods, method='POST', scope_extra={'user': SimpleUser('dave'), 'auth': AuthCredentials(['Staff', 'Editor'])})
  utest_val(b'post', resp.body)
  try: _run(Methods, method='POST', scope_extra={'user': SimpleUser('dave'), 'auth': AuthCredentials(['Staff'])})
  except HTTPException as e: utest_val(403, e.status_code)
  else: raise AssertionError('expected HTTPException')


@utest_run
def _() -> None:
  'Adapter: differing per-method requirements and missing declarations are rejected when the adapter is built.'
  class Mixed(Endpoint):
    max_body_bytes = 16
    @allow_public
    def get(self, request:PithyRequest, fields:None) -> PithyResponse: return PithyResponse(body='get')
    @requires_privileges('Staff')
    def post(self, request:PithyRequest, fields:None) -> PithyResponse: return PithyResponse(body='post')

  class Undeclared(Endpoint):
    def get(self, request:PithyRequest, fields:None) -> PithyResponse: return PithyResponse(body='get')

  utest_exc(TypeError(f"{Mixed.__qualname__}: a Starlette route applies one access policy to all methods; "
    "found [(False, []), (True, ['Staff'])]."), endpoint_adapter, Mixed)
  utest_exc(TypeError(f"{Undeclared.__qualname__} omits access declarations: ['GET']."), endpoint_route, '/u', Undeclared)


@utest_run
def _() -> None:
  'Adapter: user authentication is independent of scopes, including empty scopes and the former reserved name.'
  @allow_public
  class Privileges(Endpoint):
    def get(self, request:PithyRequest, fields:None) -> PithyResponse:
      if not request.is_authenticated:
        utest_val(frozenset(), request.privileges)
        return PithyResponse(body='anonymous')
      return PithyResponse(body=','.join(sorted(request.privileges)))

  utest_val(b'anonymous', _run(Privileges).body) # No AuthenticationMiddleware.
  utest_val(b'anonymous', _run(Privileges, scope_extra={'user': UnauthenticatedUser(), 'auth': AuthCredentials([])}).body)
  utest_val(b'anonymous', _run(Privileges, scope_extra={'auth': AuthCredentials(['authenticated', 'Staff'])}).body)
  utest_val(b'anonymous', _run(Privileges, scope_extra={
    'user': UnauthenticatedUser(), 'auth': AuthCredentials(['authenticated', 'Staff'])}).body)
  for scopes in ([], ['Staff'], ['authenticated', 'Staff']):
    utest_val(','.join(sorted(scopes)).encode(), _run(Privileges, scope_extra={
      'user': SimpleUser('dave'), 'auth': AuthCredentials(scopes)}).body)
  utest_val(b'', _run(Privileges, scope_extra={'user': SimpleUser('dave')}).body)


@utest_run
def _() -> None:
  'Adapter: authentication without scopes admits a member; denied requests neither construct handlers nor read bodies.'
  events:list[str] = []

  @requires_authenticated
  class Account(Endpoint):
    max_body_bytes = 16
    def __init__(self, request:PithyRequest, path_params:Mapping[str,object]) -> None:
      events.append('construct')
      super().__init__(request, path_params)
    def post(self, request:PithyRequest, fields:None) -> PithyResponse: return PithyResponse(body='account')

  async def receive() -> Message:
    events.append('body')
    return {'type': 'http.request', 'body': b'', 'more_body': False}

  scope:Scope = {'type': 'http', 'method': 'POST', 'scheme': 'http', 'path': '/', 'query_string': b'', 'headers': [],
    'server': ('localhost', 80), 'client': ('127.0.0.1', 1), 'path_params': {}}
  adapted = endpoint_adapter(Account)
  utest_val(True, hasattr(adapted, '__wrapped__'))
  for auth_scope in ({}, {'user': UnauthenticatedUser(), 'auth': AuthCredentials(['authenticated'])}):
    utest_exc(HTTPException(403), asyncio.run, adapted(StarletteRequest({**scope, **auth_scope}, receive)))
    utest_val([], events)
  scope.update(user=SimpleUser('dave'), auth=AuthCredentials([]))
  response = asyncio.run(adapted(StarletteRequest(scope, receive)))
  utest_val(b'account', response.body)
  utest_val(['construct', 'body'], events)
  utest_exc(HTTPException(403), _run, PrivilegedEndpoint, scope_extra={
    'user': SimpleUser('dave'), 'auth': AuthCredentials([])})
  utest_exc(HTTPException(403), _run, PrivilegedEndpoint, scope_extra={
    'user': UnauthenticatedUser(), 'auth': AuthCredentials(['Staff'])})
