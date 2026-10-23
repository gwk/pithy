# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from http import HTTPStatus

from .headers import ResponseHeadersDict


_context_keywords_ = ['bad request', 'exceptions', 'forbidden', 'http.HTTPStatus', 'method not allowed', 'not found',
  'response status', 'unauthorized', 'utf8 decoding']


class ResponseError(Exception):
  '''
  An exception that causes the current request handler to return an error response.
  Implementations can raise this as an alternative to returning a Response object.
  * status:  HTTPStatus.
  * reason: a reason phrase.

  Error responses are rendered by `pithy.web.errorrender`; `WebApp.error_response` selects the renderer.
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


class UnauthorizedError(ResponseError):
  'A ResponseError with status 401 Unauthorized: the request needs credentials it did not present, or presented invalid ones.'
  def __init__(self, reason:str='', *, headers:ResponseHeadersDict|None=None):
    super().__init__(HTTPStatus.UNAUTHORIZED, reason=reason, headers=headers)


class ForbiddenError(ResponseError):
  'A ResponseError with status 403 Forbidden: the request is understood and refused, regardless of credentials.'
  def __init__(self, reason:str='', *, headers:ResponseHeadersDict|None=None):
    super().__init__(HTTPStatus.FORBIDDEN, reason=reason, headers=headers)


class NotFoundError(ResponseError):
  'A ResponseError with status 404 Not Found.'
  def __init__(self, reason:str='', *, headers:ResponseHeadersDict|None=None):
    super().__init__(HTTPStatus.NOT_FOUND, reason=reason, headers=headers)


class MethodNotAllowedError(ResponseError):
  'A ResponseError with status 405 Method Not Allowed. Includes the mandatory Allow header.'
  def __init__(self, allowed:frozenset[str], reason:str='', *, headers:ResponseHeadersDict|None=None):
    allow_header:ResponseHeadersDict = {'allow': ', '.join(sorted(allowed))}
    combined:ResponseHeadersDict = dict(headers or {}) | allow_header
    super().__init__(HTTPStatus.METHOD_NOT_ALLOWED, reason=reason, headers=combined)


def decode_or_bad_request(data:bytes, desc:str) -> str:
  'Decode bytes to a string, or raise BadRequestError if the bytes are not valid UTF-8.'
  try:
    return data.decode()
  except UnicodeDecodeError as e:
    raise BadRequestError(f'{desc}: invalid UTF-8: {e}') from e
