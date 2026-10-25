# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from .app import WebApp
from .auth import Access, authentication_required_error, freeze_access, has_access
from .destination import Destination
from .endpoint import Endpoint, get_endpoint, GetHandler
from .errors import MethodNotAllowedError, NotFoundError
from .handler import RoutableHandler
from .request import Request
from .routetree import build_route_tree, FixedRouteKey, RouteTree
from .util import decode_path_segments


_context_keywords_ = ['dispatch', 'get functions', 'http', 'method validation', 'path matching', 'prefix tree',
  'route registration', 'typed parameters']


type RouteTarget = type[RoutableHandler]|GetHandler

type ConcealFrom = Literal['none', 'anonymous', 'unprivileged']
'The callers from whom a Router hides the routes and methods that they may not use; see `Router`.'


_setattr = object.__setattr__


class RouteNotFoundError(Exception):
  'An exception indicating that the request path did not match any route in the router.'


class Router:
  '''
  A request router that accepts RoutableHandler classes and typed GET functions.
  Functions are adapted to Endpoint classes once during construction, accepting GET and HEAD.
  The router dispatches to handler classes based on the request path,
  returning a ResolvedRoute with the matched path parameters and access requirements.
  The router splits the routes into fixed routes and pattern routes.
  Fixed routes are dispatched to via dictionary lookup.
  Pattern routes are stored in a prefix tree, which is traversed to find the appropriate endpoint for a given path.
  Routes are matched against percent-decoded path segments, so patterns are written in decoded form and handlers
  receive decoded path parameters; see `decode_path_segments`.

  Every implemented method must declare access with decorators on the handler class or its Endpoint methods.
  Missing declarations fail at registration unless `default_public=True`; explicit restrictions still apply in that mode.
  Policies are validated and frozen at registration by `freeze_access`,
  then checked by the server before construction.
  Authorization failures produce 401 for anonymous callers and 403 for authenticated callers,
  except where `conceal_from` hides the route or method.

  `conceal_from` selects the callers who see only the routes and methods that they may use:
  * 'anonymous' (the default): a path that matches no route, or a request for an unaccepted method of a route with any
    restricted method, raises the same 401 as a restricted route or method,
    so that restricted routes and methods cannot be told apart from missing ones.
    Authenticated callers receive 403, 404 and 405 as usual; the Allow header of a 405 lists every accepted method.
  * 'unprivileged': anonymous callers are treated as above.
    An authenticated caller receives 404 for a route with no method that its privileges permit,
    and otherwise 405 for any method that it may not use, with an Allow header that lists only the permitted methods.
    Routing then never raises 403. Choose this when anyone can create an account.
  * 'none': callers receive 404 and 405 for missing routes and methods, and 401 or 403 for restricted ones.
  A Router whose routes are all public has nothing to hide, and behaves as 'none'.
  The Router only conceals route-level requirements. A handler that checks access to a particular record
  must itself answer forbidden and missing records alike, e.g. with 404, to conceal which records exist.

  Field converters are resolved on initialization so programming errors with unconstructible field types raise early.
  '''

  def __init__(self, routes:Mapping[str,RouteTarget], *, default_public:bool=False,
   conceal_from:ConcealFrom='anonymous') -> None:
    if conceal_from not in ('none', 'anonymous', 'unprivileged'): raise ValueError(f'Invalid conceal_from: {conceal_from!r}.')
    policies:dict[type[RoutableHandler],frozendict[str,Access]] = {}
    handler_routes:dict[str,type[RoutableHandler]] = {}
    for path, target in routes.items():
      if isinstance(target, type):
        if not issubclass(target, RoutableHandler):
          raise TypeError(f'Route {path!r}: handler class must derive from RoutableHandler.')
        handler_cls = target
      else:
        try: handler_cls = get_endpoint(target)
        except TypeError as e: raise TypeError(f'Route {path!r}: {e}') from e
      try: policies[handler_cls] = freeze_access(handler_cls, default_public=default_public)
      except TypeError as e: raise TypeError(f'Route {path!r}: {e}') from e
      if issubclass(handler_cls, Endpoint):
        handler_cls._resolve_converters()
      handler_routes[path] = handler_cls
    self._policies = frozendict(policies)
    has_restrictions = any(required.requires_authentication for policy in policies.values() for required in policy.values())
    self._conceal_from:ConcealFrom = conceal_from if has_restrictions else 'none'
    #^ With only public routes there is nothing to conceal.
    fixed_routes, pattern_tree = build_route_tree(handler_routes)
    self.fixed_routes:dict[FixedRouteKey,type[RoutableHandler]] = fixed_routes
    self.pattern_tree:RouteTree[type[RoutableHandler]] = pattern_tree


  def resolve_route(self, request:Request) -> ResolvedRoute:
    '''
    Match the request path and method without constructing a handler; the server checks access to the result.
    Raises NotFoundError or MethodNotAllowedError, or UnauthorizedError where those would reveal a hidden route.
    With `conceal_from='unprivileged'`, it also refuses an authenticated caller the methods that its privileges do not permit,
    with 404 or 405 rather than the 403 of the server's access check.
    '''
    privileges = request.privileges
    is_authenticated = request.is_authenticated
    is_anonymous = not is_authenticated
    conceal = self._conceal_from == 'unprivileged' or (self._conceal_from == 'anonymous' and is_anonymous)
    result = self.endpoint_for_segments(request.path_segments)
    if result is None:
      if conceal and is_anonymous: raise authentication_required_error()
      raise NotFoundError
    handler_cls, path_params = result
    policy = self._policies[handler_cls]
    required = policy.get(request.method) # None if the method is not accepted.
    if conceal and is_authenticated and (required is None or not has_access(is_authenticated, privileges, required)):
      # Show an authenticated caller only the methods that its privileges permit, so that routing never raises 403.
      permitted = frozenset(method for method, req in policy.items() if has_access(is_authenticated, privileges, req))
      if not permitted: raise NotFoundError
      raise MethodNotAllowedError(permitted)
    if required is None:
      if conceal and any(req.requires_authentication for req in policy.values()): raise authentication_required_error()
      #^ The caller is anonymous here. A 405 would distinguish an unaccepted method from a restricted one,
      #  and its Allow header would list restricted methods.
      raise MethodNotAllowedError(handler_cls._methods)
    return ResolvedRoute(required_access=required, handler_cls=handler_cls, path_params=path_params)


  def endpoint_for_path(self, path:str) -> tuple[type[RoutableHandler],dict[str,Any]]|None:
    'Match a raw request path; raises BadRequestError if it cannot be decoded.'
    return self.endpoint_for_segments(decode_path_segments(path))


  def endpoint_for_segments(self, segments:list[str]) -> tuple[type[RoutableHandler],dict[str,Any]]|None:
    'Match decoded path segments, as produced by `decode_path_segments`.'
    if handler := self.fixed_routes.get(tuple(segments)):
      return (handler, {})
    return self.pattern_tree.get(segments)


class RouterApp(WebApp):
  '''
  A WebApp that uses a Router to dispatch requests to Endpoints.

  If `routes` is an existing Router, its access policies apply and the Router options must be None.
  Otherwise, `routes` is a route mapping used to construct a new Router with `default_public` and
  `conceal_from`; None selects the Router defaults.
  '''

  router:Router


  def __init__(self, routes:Mapping[str,RouteTarget]|Router, *, default_public:bool|None=None,
   conceal_from:ConcealFrom|None=None) -> None:
    if isinstance(routes, Router):
      if default_public is not None or conceal_from is not None:
        raise TypeError('Router options cannot be combined with a prebuilt Router; it already carries its settings.')
      router = routes
    else:
      router = Router(routes, default_public=False if default_public is None else default_public,
        conceal_from='anonymous' if conceal_from is None else conceal_from)
    self.router = router


  def resolve_destination(self, request:Request) -> ResolvedRoute:
    return self.router.resolve_route(request)



@dataclass(frozen=True)
class ResolvedRoute(Destination):
  'A matched route with captured parameters and frozen access requirements; no handler exists yet.'
  handler_cls:type[RoutableHandler]
  path_params:Mapping[str,object]

  def __post_init__(self) -> None:
    _setattr(self, 'path_params', frozendict(self.path_params))


  def get_handler(self, request:Request) -> RoutableHandler:
    return self.handler_cls(request=request, path_params=self.path_params)

