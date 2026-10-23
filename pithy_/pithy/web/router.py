# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .app import WebApp
from .auth import freeze_required_privileges, Privileges
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
  Policies are validated and frozen at registration by `freeze_required_privileges`,
  then checked by the server before construction.
  Authorization failures produce 401 for anonymous callers and 403 for authenticated callers.

  Field converters are resolved on initialization so programming errors with unconstructible field types raise early.
  '''

  def __init__(self, routes:Mapping[str,RouteTarget], *, default_public:bool=False) -> None:
    policies:dict[type[RoutableHandler],frozendict[str,Privileges]] = {}
    handler_routes:dict[str,type[RoutableHandler]] = {}
    for path, target in routes.items():
      if isinstance(target, type):
        if not issubclass(target, RoutableHandler):
          raise TypeError(f'Route {path!r}: handler class must derive from RoutableHandler.')
        handler_cls = target
      else:
        try: handler_cls = get_endpoint(target)
        except TypeError as e: raise TypeError(f'Route {path!r}: {e}') from e
      try: policies[handler_cls] = freeze_required_privileges(handler_cls, default_public=default_public)
      except TypeError as e: raise TypeError(f'Route {path!r}: {e}') from e
      if issubclass(handler_cls, Endpoint):
        handler_cls._resolve_converters()
      handler_routes[path] = handler_cls
    self._policies = frozendict(policies)
    fixed_routes, pattern_tree = build_route_tree(handler_routes)
    self.fixed_routes:dict[FixedRouteKey,type[RoutableHandler]] = fixed_routes
    self.pattern_tree:RouteTree[type[RoutableHandler]] = pattern_tree


  def resolve_route(self, request:Request) -> ResolvedRoute:
    '''
    Match the request path and method without checking access or constructing a handler.
    Raises NotFoundError or MethodNotAllowedError. The server authorizes the returned destination before acquisition.
    '''
    result = self.endpoint_for_segments(request.path_segments)
    if result is None: raise NotFoundError
    handler_cls, path_params = result
    if request.method not in handler_cls._methods:
      raise MethodNotAllowedError(handler_cls._methods)
    return ResolvedRoute(required_privileges=self._policies[handler_cls][request.method],
      handler_cls=handler_cls, path_params=path_params)


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

  If `routes` is an existing Router, its access policies apply and `default_public` must be None.
  Otherwise, `routes` is a route mapping used to construct a new Router with `default_public`; None means False.
  '''

  router:Router


  def __init__(self, routes:Mapping[str,RouteTarget]|Router, *, default_public:bool|None=None) -> None:
    if isinstance(routes, Router):
      if default_public is not None:
        raise TypeError('default_public cannot be combined with a prebuilt Router; it already carries the setting.')
      router = routes
    else:
      router = Router(routes, default_public=False if default_public is None else default_public)
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

