# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any

from .app import WebApp
from .endpoint import Endpoint
from .errors import MethodNotAllowedError, NotFoundError
from .handler import RequestHandler
from .request import Request
from .routetree import build_route_tree, RouteTree


class RouteNotFoundError(Exception):
  'An exception indicating that the request path did not match any route in the router.'


class Router:
  '''
  A request router that dispatches to Endpoint classes based on the request path,
  then instantiates them with the matched path parameters.
  The router splits the routes into fixed routes and pattern routes.
  Fixed routes are dispatched to via dictionary lookup.
  Pattern routes are stored in a prefix tree, which is traversed to find the appropriate endpoint for a given path.
  '''

  def __init__(self, routes:dict[str,type[Endpoint]]) -> None:
    fixed_routes, pattern_tree = build_route_tree(routes)
    self.fixed_routes:dict[str,type[Endpoint]] = fixed_routes
    self.pattern_tree:RouteTree[type[Endpoint]] = pattern_tree


  def resolve_handler(self, request:Request) -> Endpoint:
    'Dispatch the request path and return a constructed Endpoint, or raise NotFoundError/MethodNotAllowedError.'
    result = self.endpoint_for_path(request.path)
    if result is None: raise NotFoundError
    endpoint_cls, path_params = result
    if request.method not in endpoint_cls._methods:
      raise MethodNotAllowedError(endpoint_cls._methods)
    return endpoint_cls(request=request, path_params=path_params)


  def endpoint_for_path(self, path:str) -> tuple[type[Endpoint],dict[str,Any]]|None:
    if endpoint := self.fixed_routes.get(path):
      return (endpoint, {})
    return self.pattern_tree.get(path)


class RouterApp(WebApp):
  'A WebApp that uses a Router to dispatch requests to Endpoints.'

  router:Router


  def __init__(self, routes:dict[str,type[Endpoint]]|Router) -> None:
    if isinstance(routes, Router):
      router = routes
    else:
      router = Router(routes)
    self.router = router


  def resolve_handler(self, request:Request) -> RequestHandler:
    return self.router.resolve_handler(request)
