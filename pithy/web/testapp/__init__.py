# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from ..app import WebApp
from ..endpoint import Endpoint
from ..request import Request
from ..response import Response
from ..router import Router


class Hello(Endpoint):
  'Returns a plain text greeting.'

  def handle(self, request:Request) -> Response:
    return Response(body='hello', media_type='text/plain')


class EchoId(Endpoint):
  'Returns the matched integer id as plain text.'

  def handle(self, request:Request) -> Response:
    assert request.path_params is not None
    id = request.path_params['id']
    return Response(body=f'id={id}', media_type='text/plain')


class EchoName(Endpoint):
  'Returns the matched string name as plain text.'

  def handle(self, request:Request) -> Response:
    assert request.path_params is not None
    name = request.path_params['name']
    return Response(body=f'name={name}', media_type='text/plain')


_routes = {
  '/': Hello(),
  '/items/{id:nat}': EchoId(),
  '/users/{name}': EchoName(),
}


class TestApp(WebApp):

  def __init__(self) -> None:
    super().__init__(router=Router(_routes))


def main() -> None:
  from ..server import WebServer
  app = TestApp()
  server = WebServer(app=app)
  server.serve_forever()


if __name__ == '__main__': main()
