# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Mapping
from http import HTTPStatus
from typing import ClassVar

from .request import Request
from .response import Response


_context_keywords_ = ['dispatch', 'expect continue', 'http', 'request lifecycle', 'routable class']


class RequestHandler:
  'Base class for objects that handle HTTP requests. Implemented by both WebApp and RoutableHandler.'


  def handle_expect_100_continue(self, request:Request) -> Response:
    'Handle an Expect: 100-continue header. Returns CONTINUE to proceed, or an error response to reject.'
    return Response(status=HTTPStatus.CONTINUE)


  def prepare_for_request(self, request:Request) -> None:
    '''
    Prepare this handler to handle the request.

    Called after any `100-continue` negotiation and before `handle_request`.
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
  It declares what the Router relies on: construction from (request, path_params),
  `_methods`, the set of accepted HTTP methods checked before dispatch, and `_access_targets`.
  Declare access by decorating the class, or the handler methods of an Endpoint;
  see `pithy.web.auth.freeze_access`.
  '''

  _methods:ClassVar[frozenset[str]] = frozenset({'GET'})

  def __init__(self, request:Request, path_params:Mapping[str,object]) -> None:
    'Construct the handler for a single request. Subclasses override to consume path_params.'


  @classmethod
  def _access_targets(cls) -> Mapping[str,object]:
    '''
    Map accepted methods to the functions whose access decorators declare their required privileges; HEAD is never a key.
    The default is empty because these handlers can only be decorated as a whole. Endpoint returns its handler methods.
    '''
    return {}
