# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from ..endpoint import Endpoint
from ..request import Request
from ..response import TextResponse


def hello(request:Request) -> TextResponse:
  'Returns a plain text greeting.'
  return TextResponse(body='hello')


def echo_id(request:Request, id:int) -> TextResponse:
  'Returns the matched integer id as plain text.'
  return TextResponse(body=f'id={id}')


def echo_name(request:Request, name:str) -> TextResponse:
  'Returns the matched string name as plain text.'
  return TextResponse(body=f'name={name}')


class EchoBody(Endpoint):
  'Parses a urlencoded `name` field from the body'

  max_body_bytes = 32

  class Post:
    name:str

  def post(self, request:Request, fields:Post) -> TextResponse:
    return TextResponse(body=f'name={fields.name}')
