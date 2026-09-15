# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from ..endpoint import Endpoint, NoFields
from ..request import Request
from ..response import TextResponse


class Hello(Endpoint):
  'Returns a plain text greeting.'

  def get(self, request:Request, fields:NoFields) -> TextResponse:
    return TextResponse(body='hello')


class EchoId(Endpoint):
  'Returns the matched integer id as plain text.'

  class Get:
    id:int

  def get(self, request:Request, fields:Get) -> TextResponse:
    return TextResponse(body=f'id={fields.id}')


class EchoName(Endpoint):
  'Returns the matched string name as plain text.'

  class Get:
    name:str

  def get(self, request:Request, fields:Get) -> TextResponse:
    return TextResponse(body=f'name={fields.name}')


class EchoBody(Endpoint):
  'Parses a urlencoded `name` field from the body'

  max_body_bytes = 32

  class Post:
    name:str

  def post(self, request:Request, fields:Post) -> TextResponse:
    return TextResponse(body=f'name={fields.name}')
