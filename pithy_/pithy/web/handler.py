# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Mapping
from http import HTTPStatus
from typing import ClassVar

from .request import Request
from .response import Response


class RequestHandler:
  'Base class for objects that handle HTTP requests. Implemented by both WebApp and RoutableHandler.'


  def handle_expect_100_continue(self, request:Request) -> Response:
    'Handle an Expect: 100-continue header. Returns CONTINUE to proceed, or an error response to reject.'
    return Response(status=HTTPStatus.CONTINUE)


  def prepare(self, request:Request) -> None:
    '''
    Prepare to handle the request.
    This is implemented by Endpoint to read the body and fill parameters before handle_request is called.
    '''
    pass


  def handle_request(self, request:Request) -> Response:
    'Handle the request and return a response.'
    raise NotImplementedError



class RoutableHandler(RequestHandler):
  '''
  A RequestHandler that the Router constructs per matched route.
  Route-target classes (Endpoint, FilesHandler) derive from this, distinguishing them from WebApp dispatchers.
  It declares the two things the Router relies on: construction from (request, path_params),
  and `_methods`, the set of accepted HTTP methods checked before dispatch.
  '''

  _methods:ClassVar[frozenset[str]] = frozenset({'GET'})

  def __init__(self, request:Request, path_params:Mapping[str,object]) -> None:
    'Construct the handler for a single request. Subclasses override to consume path_params.'
