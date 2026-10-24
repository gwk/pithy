# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Mapping
from operator import setitem

from pithy.web.auth import _access_attr, allow_public, check_access, Privileges, requires_privileges
from pithy.web.endpoint import Endpoint, GetHandler
from pithy.web.errors import BadRequestError, ForbiddenError, MethodNotAllowedError, ResponseError, UnauthorizedError
from pithy.web.handler import RequestHandler, RoutableHandler
from pithy.web.request import Request
from pithy.web.response import Response
from pithy.web.router import ResolvedRoute, Router, RouterApp, RouteTarget
from utest import utest, utest_exc, utest_run, utest_val


def _authorized_handler(dispatcher:Router|RouterApp, request:Request) -> RequestHandler:
  'Exercise the authorization and acquisition steps that the server performs after resolution.'
  destination = dispatcher.resolve_route(request) if isinstance(dispatcher, Router) else dispatcher.resolve_destination(request)
  check_access(request.privileges, destination.required_privileges)
  return destination.get_handler(request)


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

class EpName(Endpoint):
  class Get:
    name:str
  def get(self, request:Request, fields:Get) -> Response:
    return Response(body=f'name:{fields.name}')

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
  }, default_public=True)

  utest((EpHome, {}), router.endpoint_for_path, '/')
  utest((EpAbout, {}), router.endpoint_for_path, '/about')
  utest((EpUser, {'id': 7}), router.endpoint_for_path, '/users/7')
  utest((EpStatic, {'p': 'dir/file.txt'}), router.endpoint_for_path, '/static/dir/file.txt')
  utest(None, router.endpoint_for_path, '/missing')


@utest_run
def _() -> None:
  'Router: matches percent-decoded segments and passes decoded path parameters.'
  router = Router({
    '/about': EpAbout,
    '/users/{name}': EpName,
    '/static/{p:path}': EpStatic,
  }, default_public=True)
  utest((EpAbout, {}), router.endpoint_for_path, '/ab%6Fut') # An encoded unreserved character is equivalent.
  utest((EpName, {'name': 'al ice'}), router.endpoint_for_path, '/users/al%20ice')
  utest(None, router.endpoint_for_path, '/users/a/b')
  utest((EpStatic, {'p': 'dir x/f/g.txt'}), router.endpoint_for_path, '/static/dir%20x/f/g.txt')
  utest_exc(BadRequestError, router.endpoint_for_path, '/users/%FF') # Not UTF-8.
  utest_exc(BadRequestError, router.endpoint_for_path, '/users/a%00b') # NUL.
  utest_exc(BadRequestError, router.endpoint_for_path, '/users/a%2Fb') # Encoded slash.
  utest_exc(BadRequestError, router.endpoint_for_path, '/about%2F')

  def dispatch_body(path:str) -> str|None:
    request = Request(method='GET', scheme='http', host='localhost', port=80,
      raw_path=path, query_str='', headers={}, client_addr=('127.0.0.1', 0), content_length=None)
    handler = _authorized_handler(router, request)
    response = handler.handle_request(request)
    return response.body.decode() if isinstance(response.body, (bytes, bytearray)) else None

  utest('name:caf\u00e9', dispatch_body, '/users/caf%C3%A9')
  utest('files:a/b c', dispatch_body, '/static/a/b%20c')
  utest_exc(BadRequestError, dispatch_body, '/users/%FF')


@utest_run
def _() -> None:
  'Router: resolved routes dispatch and handle requests.'
  router = Router({
    '/': EpHome,
    '/users/{id:int}': EpUser,
  }, default_public=True)

  def dispatch_body(path:str) -> str|None:
    request = Request(method='GET', scheme='http', host='localhost', port=80,
      raw_path=path, query_str='', headers={}, client_addr=('127.0.0.1', 0), content_length=None)
    try:
      handler = _authorized_handler(router, request)
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
  }, default_public=True)

  def dispatch(method:str, path:str) -> str|None:
    request = Request(method=method, scheme='http', host='localhost', port=80,
      raw_path=path, query_str='', headers={}, client_addr=('127.0.0.1', 0), content_length=None)
    try:
      handler = _authorized_handler(router, request)
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
  'Route policies authorize before handler construction; declarations are validated at registration.'

  class Open(Endpoint):
    @allow_public
    def get(self, request:Request, fields:None) -> Response: return Response(body='open')

  class Private(Endpoint):
    max_body_bytes = 16
    class Post:
      name:str
    @requires_privileges('read')
    def get(self, request:Request, fields:None) -> Response: return Response(body='private')
    @requires_privileges('write')
    def post(self, request:Request, fields:Post) -> Response: return Response(body='posted')

  @requires_privileges('read', 'write')
  class HeadOnly(RoutableHandler):
    _methods = frozenset({'HEAD'})

  class UndeclaredHead(RoutableHandler):
    _methods = frozenset({'HEAD'})

  utest_exc(TypeError, Router, {'/': UndeclaredHead})
  router = Router({'/open': Open, '/private': Private, '/head': HeadOnly})
  reader = frozenset({'authenticated', 'read'})
  writer = frozenset({'authenticated', 'read', 'write'})

  def status(method:str, path:str, privileges:Privileges) -> int:
    request = Request(method=method, scheme='http', host='localhost', port=80, raw_path=path, query_str='', headers={},
      client_addr=('127.0.0.1', 0), content_length=None, privileges=privileges)
    try: _authorized_handler(router, request)
    except ResponseError as exc: return exc.status.value
    return 200

  utest(200, status, 'GET', '/open', frozenset())
  utest(401, status, 'GET', '/private', frozenset()) # Anonymous: credentials would help.
  utest(403, status, 'GET', '/private', frozenset({'authenticated'})) # Authenticated without the privilege: they would not.
  utest(200, status, 'GET', '/private', reader)
  utest(200, status, 'HEAD', '/private', reader) # HEAD shares the GET entry.
  utest(401, status, 'HEAD', '/head', frozenset())
  utest(403, status, 'HEAD', '/head', reader) # All declared privileges are required.
  utest(200, status, 'HEAD', '/head', writer)
  utest(405, status, 'GET', '/head', writer) # Decorating the class does not add a GET handler.
  utest(403, status, 'POST', '/private', reader)
  utest(200, status, 'POST', '/private', writer)
  utest(405, status, 'PUT', '/private', reader) # Method negotiation precedes authorization.
  utest(404, status, 'GET', '/missing', reader) # Anonymous callers instead get 401; see the concealment test.

  class Undeclared(Endpoint):
    def get(self, request:Request, fields:None) -> Response: return Response(body='')

  class Partial(Endpoint):
    max_body_bytes = 16
    @allow_public
    def get(self, request:Request, fields:None) -> Response: return Response(body='')
    def post(self, request:Request, fields:None) -> Response: return Response(body='')

  @allow_public
  class Both(Endpoint):
    @requires_privileges('read')
    def get(self, request:Request, fields:None) -> Response: return Response(body='')

  def fn(request:Request) -> Response: return Response(body='')

  utest_exc(TypeError, Router, {'/': Undeclared})
  utest_exc(TypeError, Router, {'/': Partial})
  utest_exc(TypeError("Route '/': " f'{Both.__qualname__} declares access on both the class and handler methods: '
    "['GET']."), Router, {'/': Both})
  utest_exc(TypeError, Router, {'/': Both}, default_public=True)
  utest_exc(TypeError, Router, {'/': fn}) # A function target must declare access.
  Router({'/': Undeclared, '/fn': fn}, default_public=True) # Opting out admits both.


@utest_run
def _() -> None:
  'Router: overlapping route patterns are rejected at construction (mounts get shadow-checking for free).'
  utest_exc(ValueError, Router, {'/x/{a:path}': EpHome, '/x/{b:path}': EpAbout}, default_public=True)


@utest_run
def _() -> None:
  'Router: accepts a mix of Endpoint classes, other handler classes and functions, adapting functions at registration.'
  def user(request:Request, id:int, *, note:str|None) -> Response:
    return Response(body=f'{request.method}:{id}:{note!r}')

  # The same function may be registered for several routes.
  routes:Mapping[str,RouteTarget] = {
    '/': EpHome, '/users/{id:int}': user, '/members/{id:int}': user, '/static/{subpath:path}': HandlerFiles}
  app = RouterApp(routes, default_public=True)
  match = app.router.endpoint_for_path('/users/7')
  assert match is not None
  handler_cls, params = match
  utest_val(True, issubclass(handler_cls, Endpoint))
  utest_val({'id': 7}, params)

  def dispatch(method:str, path:str, query_str:str='') -> bytes|bytearray|None:
    request = Request(method=method, scheme='http', host='localhost', port=80,
      raw_path=path, query_str=query_str, headers={}, client_addr=('127.0.0.1', 0), content_length=None)
    handler = _authorized_handler(app, request)
    handler.prepare_for_request(request)
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
  Router(class_routes, default_public=True)
  RouterApp(function_routes, default_public=True)


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
    'use optional field types for missing values.'), Router, {'/d': default}, default_public=True)
  # The converters of adapted functions are resolved at registration.
  utest_exc(TypeError(f'{unsupported.__qualname__}.Get.value: no converter is available for field type {Left|Right!r}.'),
    Router, {'/': unsupported}, default_public=True)
  utest_exc(TypeError("Route '/': handler class must derive from RoutableHandler."), Router, {'/': object}, default_public=True)


@utest_run
def _() -> None:
  'Function routes retain their declarations, enforce before field parsing, and share GET policy with HEAD.'
  @requires_privileges('authenticated')
  def account(request:Request, uid:int) -> Response:
    return Response(body=str(uid))

  @allow_public
  def home(request:Request) -> Response: return Response(body='home')

  def undeclared(request:Request) -> Response: return Response(body='default')

  router = Router({'/account/{uid}': account, '/home': home})
  public_req = Request(method='GET', scheme='http', host='localhost', port=80, raw_path='/home', query_str='',
    headers={}, client_addr=('127.0.0.1', 0), content_length=None)
  utest_val(b'home', _authorized_handler(router, public_req).handle_request(public_req).body)
  req = Request(method='GET', scheme='http', host='localhost', port=80, raw_path='/account/not-an-int', query_str='',
    headers={}, client_addr=('127.0.0.1', 0), content_length=None)
  destination = router.resolve_route(req) # Resolution neither authorizes nor converts the invalid uid.
  utest_val(frozenset({'authenticated'}), destination.required_privileges)
  utest_val({'uid': 'not-an-int'}, destination.path_params)
  utest_exc(UnauthorizedError, _authorized_handler, router, req) # Before the invalid uid is converted.
  req.privileges = frozenset({'authenticated'})
  utest_exc(BadRequestError, _authorized_handler, router, req)
  req = Request(method='HEAD', scheme='http', host='localhost', port=80, raw_path='/account/7', query_str='',
    headers={}, client_addr=('127.0.0.1', 0), content_length=None, privileges=frozenset({'authenticated'}))
  utest_val(b'7', _authorized_handler(router, req).handle_request(req).body)
  req.privileges = frozenset()
  utest_exc(UnauthorizedError, _authorized_handler, router, req)
  utest_exc(TypeError, Router, {'/': undeclared})

  default_router = Router({'/account/{uid}': account, '/': undeclared}, default_public=True)
  utest_exc(UnauthorizedError, _authorized_handler, default_router, req)
  req = Request(method='GET', scheme='http', host='localhost', port=80, raw_path='/', query_str='',
    headers={}, client_addr=('127.0.0.1', 0), content_length=None)
  utest_val(b'default', _authorized_handler(default_router, req).handle_request(req).body)
  utest_val(router, RouterApp(router).router)
  for default in (False, True):
    utest_exc(TypeError, RouterApp, router, default_public=default)

  # Replacing function metadata cannot change an already registered route.
  setattr(account, _access_attr, frozenset())
  req = Request(method='GET', scheme='http', host='localhost', port=80, raw_path='/account/7', query_str='',
    headers={}, client_addr=('127.0.0.1', 0), content_length=None)
  utest_exc(UnauthorizedError, _authorized_handler, router, req)


@utest_run
def _() -> None:
  'Access declared by a class decorator covers every accepted method, is inherited, and is snapshotted at registration.'

  @requires_privileges('authenticated')
  class Account(Endpoint):
    max_body_bytes = 16
    def get(self, request:Request, fields:None) -> Response: return Response(body='account')
    def post(self, request:Request, fields:None) -> Response: return Response(body='posted')

  @requires_privileges('read')
  class Restricted(RoutableHandler):
    _methods = frozenset({'GET', 'HEAD', 'POST'})
    def __init__(self, request:Request, path_params:Mapping[str,object]) -> None:
      raise AssertionError('Denied requests must not construct handlers.')

  class Inherited(Restricted): pass

  @allow_public
  class Redeclared(Restricted): pass

  router = Router({'/account': Account, '/restricted': Restricted, '/inherited': Inherited, '/redeclared': Redeclared})

  def required(method:str, path:str) -> Privileges:
    request = Request(method=method, scheme='http', host='localhost', port=80, raw_path=path, query_str='', headers={},
      client_addr=('127.0.0.1', 0), content_length=None)
    return router.resolve_route(request).required_privileges

  for method in ('GET', 'HEAD', 'POST'):
    utest(frozenset({'authenticated'}), required, method, '/account')
    utest(frozenset({'read'}), required, method, '/restricted')
    utest(frozenset({'read'}), required, method, '/inherited')
    utest(frozenset(), required, method, '/redeclared')

  # Replacing class metadata cannot open an already registered route.
  setattr(Restricted, _access_attr, frozenset())
  req = Request(method='POST', scheme='http', host='localhost', port=80, raw_path='/inherited', query_str='',
    headers={}, client_addr=('127.0.0.1', 0), content_length=None)
  utest_exc(UnauthorizedError, _authorized_handler, router, req)
  req.privileges = frozenset({'authenticated'})
  utest_exc(ForbiddenError, _authorized_handler, router, req)


@utest_run
def _() -> None:
  'Anonymous callers see only the public surface; hidden routes raise the same 401 as restricted routes.'

  class Mixed(Endpoint):
    max_body_bytes = 16
    @allow_public
    def get(self, request:Request, fields:None) -> Response: return Response(body='mixed')
    @requires_privileges('write')
    def post(self, request:Request, fields:None) -> Response: return Response(body='posted')

  @requires_privileges('read')
  class Private(Endpoint):
    def get(self, request:Request, fields:None) -> Response: return Response(body='private')

  @allow_public
  class Open(Endpoint):
    def get(self, request:Request, fields:None) -> Response: return Response(body='open')

  @requires_privileges('read')
  class Daily(RoutableHandler): pass

  routes:dict[str,RouteTarget] = {'/mixed': Mixed, '/private': Private, '/daily/{day:date}': Daily}
  reader = frozenset({'authenticated', 'read'})

  def outcome(dispatcher:Router|RouterApp, method:str, path:str, privileges:Privileges=frozenset()) -> tuple[int,str]:
    request = Request(method=method, scheme='http', host='localhost', port=80, raw_path=path, query_str='', headers={},
      client_addr=('127.0.0.1', 0), content_length=None, privileges=privileges)
    try: _authorized_handler(dispatcher, request)
    except ResponseError as exc: return (exc.status.value, exc.reason)
    return (200, '')

  hidden = (401, 'Authentication required.')
  router = Router(routes)
  utest(hidden, outcome, router, 'GET', '/private') # Restricted route.
  utest(hidden, outcome, router, 'GET', '/missing') # Indistinguishable from the restricted route.
  utest(hidden, outcome, router, 'PUT', '/private') # A route without public methods hides its methods too.
  utest(hidden, outcome, router, 'POST', '/mixed') # Restricted method of a route with a public method.
  utest(hidden, outcome, router, 'PUT', '/mixed') # Indistinguishable from the restricted method.
  utest((200, ''), outcome, router, 'GET', '/mixed')
  utest(405, lambda: outcome(router, 'PUT', '/mixed', reader)[0])
  utest(404, lambda: outcome(router, 'GET', '/missing', reader)[0])
  utest(405, lambda: outcome(router, 'PUT', '/private', reader)[0])
  # A well formed segment with an impossible value is a nonmatch; a conversion error would answer 500 and reveal the pattern.
  utest(hidden, outcome, router, 'GET', '/daily/2026-02-28')
  utest(hidden, outcome, router, 'GET', '/daily/2026-02-30')
  utest(404, lambda: outcome(router, 'GET', '/daily/2026-02-30', reader)[0])

  revealing = Router(routes, conceal_from='none')
  utest(404, lambda: outcome(revealing, 'GET', '/missing')[0])
  utest(404, lambda: outcome(revealing, 'GET', '/daily/2026-02-30')[0])
  utest(405, lambda: outcome(revealing, 'PUT', '/private')[0])
  utest(405, lambda: outcome(revealing, 'PUT', '/mixed')[0])
  utest(404, lambda: outcome(Router({'/open': Open}), 'GET', '/missing')[0]) # Nothing to conceal.

  utest(hidden, outcome, RouterApp(routes), 'GET', '/missing')
  utest(404, lambda: outcome(RouterApp(routes, conceal_from='none'), 'GET', '/missing')[0])
  utest_exc(TypeError, RouterApp, router, conceal_from='anonymous')
  utest_exc(ValueError, Router, routes, conceal_from='everyone')

  def allowed(dispatcher:Router, method:str, path:str, privileges:Privileges) -> tuple[int,str|None]:
    request = Request(method=method, scheme='http', host='localhost', port=80, raw_path=path, query_str='', headers={},
      client_addr=('127.0.0.1', 0), content_length=None, privileges=privileges)
    try: _authorized_handler(dispatcher, request)
    except ResponseError as exc:
      allow = (exc.headers or {}).get('allow')
      return (exc.status.value, None if allow is None else str(allow))
    return (200, None)

  # Concealing from unprivileged callers shows each authenticated caller only the methods that it may use.
  member = frozenset({'authenticated'})
  writer = reader | {'write'}
  strict = Router(routes, conceal_from='unprivileged')
  utest(hidden, outcome, strict, 'GET', '/missing') # Anonymous callers are treated as with the default.
  utest(hidden, outcome, strict, 'GET', '/private')
  utest(hidden, outcome, strict, 'PUT', '/mixed')
  utest((200, ''), outcome, strict, 'GET', '/mixed')
  utest((404, None), allowed, strict, 'GET', '/missing', member)
  utest((404, None), allowed, strict, 'GET', '/private', member) # Indistinguishable from the missing route.
  utest((404, None), allowed, strict, 'PUT', '/private', member)
  utest((404, None), allowed, strict, 'GET', '/daily/2026-02-28', member)
  utest((405, 'GET, HEAD'), allowed, strict, 'POST', '/mixed', member) # The Allow header omits the restricted POST.
  utest((405, 'GET, HEAD'), allowed, strict, 'PUT', '/mixed', member) # Indistinguishable from the restricted method.
  utest((200, None), allowed, strict, 'GET', '/private', reader)
  utest((405, 'GET, HEAD'), allowed, strict, 'PUT', '/private', reader)
  utest((405, 'GET, HEAD'), allowed, strict, 'POST', '/mixed', reader)
  utest((200, None), allowed, strict, 'POST', '/mixed', writer)
  utest((405, 'GET, HEAD, POST'), allowed, strict, 'PUT', '/mixed', writer)
  utest((404, None), allowed, Router({'/open': Open}, conceal_from='unprivileged'), 'GET', '/missing', frozenset())
  #^ Nothing to conceal.
  utest((405, 'GET, HEAD, POST'), allowed, Router(routes), 'PUT', '/mixed', member) # The default reveals POST.
  utest((403, None), allowed, Router(routes), 'GET', '/private', member)


@utest_run
def _() -> None:
  'A resolved route owns a read-only snapshot of its captured parameters.'
  params:dict[str,object] = {'id': 7}
  destination = ResolvedRoute(required_privileges=frozenset(), handler_cls=EpUser, path_params=params)
  params['id'] = 8
  utest_val({'id': 7}, destination.path_params)
  utest_exc(TypeError, setitem, destination.path_params, 'id', 9)
