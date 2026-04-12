# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from http import HTTPStatus

from .request import Request
from .response import Response


class RequestHandler:
  'Base class for objects that handle HTTP requests. Implemented by both WebApp and ResolvedRoute.'


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
