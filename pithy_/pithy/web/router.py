# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Mapping
from typing import Any

from .app import WebApp
from .endpoint import Endpoint, get_endpoint, GetHandler
from .errors import MethodNotAllowedError, NotFoundError
from .handler import RequestHandler, RoutableHandler
from .request import Request
from .routetree import build_route_tree, FixedRouteKey, RouteTree
from .util import decode_path_segments


_context_keywords_ = ['dispatch', 'get functions', 'http', 'method validation', 'path matching', 'prefix tree',
  'route registration', 'typed parameters']


type RouteTarget = type[RoutableHandler]|GetHandler


class RouteNotFoundError(Exception):
  'An exception indicating that the request path did not match any route in the router.'


class Router:
  '''
  A request router that accepts RoutableHandler classes and typed GET functions.
  Functions are adapted to Endpoint classes once during construction, accepting GET and HEAD.
  The router dispatches to handler classes based on the request path,
  then instantiates them with the matched path parameters.
  The router splits the routes into fixed routes and pattern routes.
  Fixed routes are dispatched to via dictionary lookup.
  Pattern routes are stored in a prefix tree, which is traversed to find the appropriate endpoint for a given path.
  Routes are matched against percent-decoded path segments, so patterns are written in decoded form and handlers
  receive decoded path parameters; see `decode_path_segments`.

  Field converters are resolved on initialization so programming errors with unconstructible field types raise early.
  '''

  def __init__(self, routes:Mapping[str,RouteTarget]) -> None:
    handler_routes:dict[str,type[RoutableHandler]] = {}
    for path, target in routes.items():
      if isinstance(target, type):
        if not issubclass(target, RoutableHandler):
          raise TypeError(f'Route {path!r}: handler class must derive from RoutableHandler.')
        handler_cls = target
      else:
        try: handler_cls = get_endpoint(target)
        except TypeError as e: raise TypeError(f'Route {path!r}: {e}') from e
      if issubclass(handler_cls, Endpoint):
        handler_cls._resolve_converters()
      handler_routes[path] = handler_cls
    fixed_routes, pattern_tree = build_route_tree(handler_routes)
    self.fixed_routes:dict[FixedRouteKey,type[RoutableHandler]] = fixed_routes
    self.pattern_tree:RouteTree[type[RoutableHandler]] = pattern_tree


  def resolve_handler(self, request:Request) -> RoutableHandler:
    'Dispatch the request path and return a constructed handler, or raise NotFoundError/MethodNotAllowedError.'
    result = self.endpoint_for_segments(request.path_segments)
    if result is None: raise NotFoundError
    handler_cls, path_params = result
    if request.method not in handler_cls._methods:
      raise MethodNotAllowedError(handler_cls._methods)
    return handler_cls(request=request, path_params=path_params)


  def endpoint_for_path(self, path:str) -> tuple[type[RoutableHandler],dict[str,Any]]|None:
    'Match a raw request path; raises BadRequestError if it cannot be decoded.'
    return self.endpoint_for_segments(decode_path_segments(path))


  def endpoint_for_segments(self, segments:list[str]) -> tuple[type[RoutableHandler],dict[str,Any]]|None:
    'Match decoded path segments, as produced by `decode_path_segments`.'
    if handler := self.fixed_routes.get(tuple(segments)):
      return (handler, {})
    return self.pattern_tree.get(segments)


class RouterApp(WebApp):
  'A WebApp that uses a Router to dispatch requests to Endpoints.'

  router:Router


  def __init__(self, routes:Mapping[str,RouteTarget]|Router) -> None:
    if isinstance(routes, Router):
      router = routes
    else:
      router = Router(routes)
    self.router = router


  def resolve_handler(self, request:Request) -> RequestHandler:
    return self.router.resolve_handler(request)
