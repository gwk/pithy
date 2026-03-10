# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from __future__ import annotations

from http import HTTPStatus

from .errors import ResponseError
from .request import Request
from .response import Response


class WebApp:

  def handle_expect_100_continue(self, request:Request) -> Response:
    return Response(status=HTTPStatus.CONTINUE)


  def handle_request(self, request:Request) -> Response:
    raise ResponseError(status=HTTPStatus.NOT_IMPLEMENTED)
