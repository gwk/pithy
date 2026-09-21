# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Mapping
from typing import Any

from .app import WebApp
from .endpoint import Endpoint, get_endpoint, GetHandler
from .errors import MethodNotAllowedError, NotFoundError
from .handler import RequestHandler, RoutableHandler
from .request import Request
from .routetree import build_route_tree, RouteTree


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
    self.fixed_routes:dict[str,type[RoutableHandler]] = fixed_routes
    self.pattern_tree:RouteTree[type[RoutableHandler]] = pattern_tree


  def resolve_handler(self, request:Request) -> RoutableHandler:
    'Dispatch the request path and return a constructed handler, or raise NotFoundError/MethodNotAllowedError.'
    result = self.endpoint_for_path(request.path)
    if result is None: raise NotFoundError
    handler_cls, path_params = result
    if request.method not in handler_cls._methods:
      raise MethodNotAllowedError(handler_cls._methods)
    return handler_cls(request=request, path_params=path_params)


  def endpoint_for_path(self, path:str) -> tuple[type[RoutableHandler],dict[str,Any]]|None:
    if handler := self.fixed_routes.get(path):
      return (handler, {})
    return self.pattern_tree.get(path)


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
