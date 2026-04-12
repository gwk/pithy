# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from ..endpoint import Endpoint
from ..request import Request
from ..response import Response
from ..router import Router, RouterApp


class Hello(Endpoint):
  'Returns a plain text greeting.'

  def handle_request(self, request:Request) -> Response:
    return Response(body='hello', media_type='text/plain')


class EchoId(Endpoint):
  'Returns the matched integer id as plain text.'
  id:int

  def handle_request(self, request:Request) -> Response:
    return Response(body=f'id={self.id}', media_type='text/plain')


class EchoName(Endpoint):
  'Returns the matched string name as plain text.'
  name:str

  def handle_request(self, request:Request) -> Response:
    return Response(body=f'name={self.name}', media_type='text/plain')


_routes:dict[str,type[Endpoint]] = {
  '/': Hello,
  '/items/{id:nat}': EchoId,
  '/users/{name}': EchoName,
}


class TestApp(RouterApp):

  def __init__(self) -> None:
    super().__init__(router=Router(_routes))
