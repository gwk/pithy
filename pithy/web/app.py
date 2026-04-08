# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from __future__ import annotations

from http import HTTPStatus

from .errors import ResponseError, ResponseNotFound
from .request import Request
from .response import Response
from .router import Router


class WebApp:

  def __init__(self, router:Router|None=None) -> None:
    self.router = router


  def handle_expect_100_continue(self, request:Request) -> Response:
    if self.router is not None:
      result = self.router.endpoint_for_path(request.path)
      if result is None: raise ResponseNotFound
      _, path_params = result
      request.path_params = path_params
    return Response(status=HTTPStatus.CONTINUE)


  def handle_request(self, request:Request) -> Response:
    if self.router is not None:
      result = self.router.endpoint_for_path(request.path)
      if result is None: raise ResponseNotFound
      endpoint, path_params = result
      request.path_params = path_params
      return endpoint.handle(request)
    raise ResponseError(status=HTTPStatus.NOT_IMPLEMENTED)
