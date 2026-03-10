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

  def __init__(self, status:HTTPStatus, reason:str='', headers:ResponseHeadersDict|None=None):
    self.status = status
    self.reason = reason
    self.headers = headers
    super().__init__(f'{status}: {reason}')


ResponseNotFound = ResponseError(HTTPStatus.NOT_FOUND)
ResponseNotImplemented = ResponseError(HTTPStatus.NOT_IMPLEMENTED)


def BadRequest(reason:str='') -> ResponseError:
  return ResponseError(HTTPStatus.BAD_REQUEST, reason=reason)
