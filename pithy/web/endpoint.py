# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from .request import Request
from .response import Response


class Endpoint:

  def handle(self, request:Request) -> Response:
    raise NotImplementedError
