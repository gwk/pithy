# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from ..endpoint import Endpoint
from ..request import Request
from ..response import TextResponse


class Hello(Endpoint):
  'Returns a plain text greeting.'

  def handle_request(self, request:Request) -> TextResponse:
    return TextResponse(body='hello')


class EchoId(Endpoint):
  'Returns the matched integer id as plain text.'

  class Fields:
    id:int
  fields:Fields

  def handle_request(self, request:Request) -> TextResponse:
    return TextResponse(body=f'id={self.fields.id}')


class EchoName(Endpoint):
  'Returns the matched string name as plain text.'

  class Fields:
    name:str
  fields:Fields

  def handle_request(self, request:Request) -> TextResponse:
    return TextResponse(body=f'name={self.fields.name}')


class EchoBody(Endpoint):
  'Parses a urlencoded `name` field from the body'

  methods = 'POST'
  max_body_bytes = 32

  class Fields:
    name:str
  fields:Fields

  def handle_request(self, request:Request) -> TextResponse:
    return TextResponse(body=f'name={self.fields.name}')
