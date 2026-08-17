# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Error types for the B2 native API, and pure retry policy helpers.
'''

from pithy.json import parse_json


max_retry_delay = 64.0


class B2Error(Exception):
  '''
  An error response from the B2 API.
  `status` is the HTTP status code; `code` and `message` come from the standard JSON error body.
  `retry_after` is the parsed Retry-After header in seconds, when the server provides one.
  '''

  def __init__(self, status:int, code:str, message:str, *, retry_after:float|None=None) -> None:
    super().__init__(status, code, message)
    self.status = status
    self.code = code
    self.message = message
    self.retry_after = retry_after

  def __str__(self) -> str: return f'B2 API error: status {self.status}; code {self.code!r}; {self.message}'


class B2Unauthorized(B2Error):
  'The credentials or auth token were rejected: 401 with code "unauthorized" or "bad_auth_token".'

class B2ExpiredAuthToken(B2Error):
  'The account auth token has expired: 401 with code "expired_auth_token". Reauthorizing should succeed.'

class B2NotFound(B2Error):
  'The requested entity does not exist: 404.'

class B2TooManyRequests(B2Error):
  'The request was rate limited: 429. Retry after a delay.'

class B2ServiceUnavailable(B2Error):
  'The service or upload URL is unavailable: 503. Retry after a delay.'

class B2ServerError(B2Error):
  'An internal server error: any other 5xx. Retry after a delay.'

class B2IntegrityError(B2Error):
  'A downloaded body did not match the length or SHA1 that the server reported.'


def b2_error_for_response(status:int, body:str, *, retry_after:float|None=None) -> B2Error:
  '''
  Create the appropriate B2Error subclass for an error response.
  The standard error body is JSON `{"status":..., "code":..., "message":...}`; a non-JSON body is tolerated.
  '''
  code = ''
  message = body
  try: parsed = parse_json(body)
  except ValueError: pass
  else:
    if isinstance(parsed, dict):
      code = str(parsed.get('code') or '')
      message = str(parsed.get('message') or '')
  if status == 401:
    if code == 'expired_auth_token': return B2ExpiredAuthToken(status, code, message, retry_after=retry_after)
    return B2Unauthorized(status, code, message, retry_after=retry_after)
  if status == 404: return B2NotFound(status, code, message, retry_after=retry_after)
  if status == 429: return B2TooManyRequests(status, code, message, retry_after=retry_after)
  if status == 503: return B2ServiceUnavailable(status, code, message, retry_after=retry_after)
  if status >= 500: return B2ServerError(status, code, message, retry_after=retry_after)
  return B2Error(status, code, message, retry_after=retry_after)


def is_retryable(error:B2Error) -> bool:
  'True for the statuses that the B2 documentation directs clients to retry: 429, 503, and other 5xx.'
  return isinstance(error, (B2TooManyRequests, B2ServiceUnavailable, B2ServerError))


def retry_delay(attempt:int, retry_after:float|None=None) -> float:
  '''
  Delay in seconds before retry number `attempt` (zero-based).
  A server-provided Retry-After takes precedence; otherwise exponential backoff from one second, capped.
  '''
  if retry_after is not None: return retry_after
  return min(2.0**attempt, max_retry_delay)
