# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any

from .endpoint import Endpoint
from .routetree import build_route_tree, RouteTree


class RouteNotFoundError(Exception):
  'An exception indicating that the request path did not match any route in the router.'


class Router:
  '''
  A request router that dispatches to Endpoint objects based on the request path.
  The router splits the routes into fixed routes and pattern routes.
  Fixed routes are dispatched to via dictionary lookup.
  Pattern routes are stored in a prefix tree, which is traversed to find the appropriate endpoint for a given path.
  '''

  def __init__(self, routes:dict[str,Endpoint]) -> None:
    fixed_routes, pattern_tree = build_route_tree(routes)
    self.fixed_routes:dict[str,Endpoint] = fixed_routes
    self.pattern_tree:RouteTree[Endpoint] = pattern_tree


  def endpoint_for_path(self, path:str) -> tuple[Endpoint,dict[str,Any]]|None:
    if endpoint := self.fixed_routes.get(path):
      return (endpoint, {})
    return self.pattern_tree.get(path)
