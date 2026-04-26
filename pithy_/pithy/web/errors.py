# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from http import HTTPStatus

from .headers import ResponseHeadersDict


class ResponseError(Exception):
  '''
  An exception that causes the current request handler to return an error response.
  Implementations can raise this as an alternative to returning a Response object.
  * status:  HTTPStatus.
  * reason: a reason phrase.

  TODO: the generated response should generate a body depending on a specified content type.
  This will allow users to serve HTML, JSON, or any other kind of error they need.
  Perhaps the best way to do it is to move response() to WebApp.
  '''

  def __init__(self, status:HTTPStatus, reason:str='', *, headers:ResponseHeadersDict|None=None):
    self.status = status
    self.reason = reason
    self.headers = headers
    super().__init__(f'{status}: {reason}')


class BadRequestError(ResponseError):
  'A ResponseError with status 400 Bad Request.'
  def __init__(self, reason:str='', *, headers:ResponseHeadersDict|None=None):
    super().__init__(HTTPStatus.BAD_REQUEST, reason=reason, headers=headers)


class NotFoundError(ResponseError):
  'A ResponseError with status 404 Not Found.'
  def __init__(self, reason:str='', *, headers:ResponseHeadersDict|None=None):
    super().__init__(HTTPStatus.NOT_FOUND, reason=reason, headers=headers)


def decode_or_bad_request(data:bytes, desc:str) -> str:
  'Decode bytes to a string, or raise BadRequestError if the bytes are not valid UTF-8.'
  try:
    return data.decode()
  except UnicodeDecodeError as e:
    raise BadRequestError(f'{desc}: invalid UTF-8: {e}') from e
