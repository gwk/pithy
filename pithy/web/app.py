# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from http import HTTPStatus

from .errors import ResponseError
from .handler import RequestHandler
from .request import Request
from .response import Response


class WebApp(RequestHandler):

  def resolve_handler(self, request:Request) -> RequestHandler:
    'Resolve the handler for a request. Override to implement routing.'
    return self


  def handle_request(self, request:Request) -> Response:
    raise ResponseError(status=HTTPStatus.NOT_IMPLEMENTED)
