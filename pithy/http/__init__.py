# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from http import HTTPMethod, HTTPStatus
from wsgiref.handlers import format_date_time


http_method_bytes_to_enums = { m.value.encode('latin1') : m for m in HTTPMethod }

# Informational responses.
CONTINUE = HTTPStatus.CONTINUE
SWITCHING_PROTOCOLS = HTTPStatus.SWITCHING_PROTOCOLS
PROCESSING = HTTPStatus.PROCESSING
EARLY_HINTS = HTTPStatus.EARLY_HINTS

# Success.
OK = HTTPStatus.OK
CREATED = HTTPStatus.CREATED
ACCEPTED = HTTPStatus.ACCEPTED
NON_AUTHORITATIVE_INFORMATION = HTTPStatus.NON_AUTHORITATIVE_INFORMATION
NO_CONTENT = HTTPStatus.NO_CONTENT
RESET_CONTENT = HTTPStatus.RESET_CONTENT
PARTIAL_CONTENT = HTTPStatus.PARTIAL_CONTENT
MULTI_STATUS = HTTPStatus.MULTI_STATUS
ALREADY_REPORTED = HTTPStatus.ALREADY_REPORTED
IM_USED = HTTPStatus.IM_USED

# Redirection.
MULTIPLE_CHOICES = HTTPStatus.MULTIPLE_CHOICES
MOVED_PERMANENTLY = HTTPStatus.MOVED_PERMANENTLY
FOUND = HTTPStatus.FOUND
SEE_OTHER = HTTPStatus.SEE_OTHER
NOT_MODIFIED = HTTPStatus.NOT_MODIFIED
USE_PROXY = HTTPStatus.USE_PROXY
TEMPORARY_REDIRECT = HTTPStatus.TEMPORARY_REDIRECT
PERMANENT_REDIRECT = HTTPStatus.PERMANENT_REDIRECT

# Client error.
BAD_REQUEST = HTTPStatus.BAD_REQUEST
UNAUTHORIZED = HTTPStatus.UNAUTHORIZED
PAYMENT_REQUIRED = HTTPStatus.PAYMENT_REQUIRED
FORBIDDEN = HTTPStatus.FORBIDDEN
NOT_FOUND = HTTPStatus.NOT_FOUND
METHOD_NOT_ALLOWED = HTTPStatus.METHOD_NOT_ALLOWED
NOT_ACCEPTABLE = HTTPStatus.NOT_ACCEPTABLE
PROXY_AUTHENTICATION_REQUIRED = HTTPStatus.PROXY_AUTHENTICATION_REQUIRED
REQUEST_TIMEOUT = HTTPStatus.REQUEST_TIMEOUT
CONFLICT = HTTPStatus.CONFLICT
GONE = HTTPStatus.GONE
LENGTH_REQUIRED = HTTPStatus.LENGTH_REQUIRED
PRECONDITION_FAILED = HTTPStatus.PRECONDITION_FAILED
REQUEST_ENTITY_TOO_LARGE = HTTPStatus.REQUEST_ENTITY_TOO_LARGE
REQUEST_URI_TOO_LONG = HTTPStatus.REQUEST_URI_TOO_LONG
UNSUPPORTED_MEDIA_TYPE = HTTPStatus.UNSUPPORTED_MEDIA_TYPE
REQUESTED_RANGE_NOT_SATISFIABLE = HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE
EXPECTATION_FAILED = HTTPStatus.EXPECTATION_FAILED
IM_A_TEAPOT = HTTPStatus.IM_A_TEAPOT
MISDIRECTED_REQUEST = HTTPStatus.MISDIRECTED_REQUEST
UNPROCESSABLE_ENTITY = HTTPStatus.UNPROCESSABLE_ENTITY
LOCKED = HTTPStatus.LOCKED
FAILED_DEPENDENCY = HTTPStatus.FAILED_DEPENDENCY
TOO_EARLY = HTTPStatus.TOO_EARLY
UPGRADE_REQUIRED = HTTPStatus.UPGRADE_REQUIRED
PRECONDITION_REQUIRED = HTTPStatus.PRECONDITION_REQUIRED
TOO_MANY_REQUESTS = HTTPStatus.TOO_MANY_REQUESTS
REQUEST_HEADER_FIELDS_TOO_LARGE = HTTPStatus.REQUEST_HEADER_FIELDS_TOO_LARGE
UNAVAILABLE_FOR_LEGAL_REASONS = HTTPStatus.UNAVAILABLE_FOR_LEGAL_REASONS

# Server error.
INTERNAL_SERVER_ERROR = HTTPStatus.INTERNAL_SERVER_ERROR
NOT_IMPLEMENTED = HTTPStatus.NOT_IMPLEMENTED
BAD_GATEWAY = HTTPStatus.BAD_GATEWAY
SERVICE_UNAVAILABLE = HTTPStatus.SERVICE_UNAVAILABLE
GATEWAY_TIMEOUT = HTTPStatus.GATEWAY_TIMEOUT
HTTP_VERSION_NOT_SUPPORTED = HTTPStatus.HTTP_VERSION_NOT_SUPPORTED
VARIANT_ALSO_NEGOTIATES = HTTPStatus.VARIANT_ALSO_NEGOTIATES
INSUFFICIENT_STORAGE = HTTPStatus.INSUFFICIENT_STORAGE
LOOP_DETECTED = HTTPStatus.LOOP_DETECTED
NOT_EXTENDED = HTTPStatus.NOT_EXTENDED
NETWORK_AUTHENTICATION_REQUIRED = HTTPStatus.NETWORK_AUTHENTICATION_REQUIRED


non_body_statuses:tuple[HTTPStatus,...] = (
  NO_CONTENT,
  RESET_CONTENT, # Note: RFC 7230 3.3 does not mention 205 RESET CONTENT but RFC 7231 6.3.6 does.
  NOT_MODIFIED,
)


# Prerender HTTP status messages.
http_status_versioned_response_bytes = { s : b'HTTP/1.1 %d %s' % (s.value, s.phrase.encode('latin1')) for s in HTTPStatus }

http_status_response_strings = { s : f'{s.value} {s.phrase}'  for s in HTTPStatus }


class HttpException(Exception):

  def __init__(self, status:HTTPStatus, message:str='') -> None:
    self.status = status
    self.message = message

  def __str__(self) -> str:
    msg = self.message
    if not msg and self.__cause__: msg = str(self.__cause__)
    return f'{self.status.value} {self.status.phrase}' + (f': {msg}' if msg else '')


def response_status_line_for_exc(exc:Exception, dbg:bool) -> bytes:
  '''
  Return an appropriate status line for an exception.
  If the exception is an HttpException, use its status and message.
  Otherwise, use a 500 status; only include the exception message if `dbg` is True.
  The returned line includes the terminating CRLF.
  '''
  if isinstance(exc, HttpException):
    status = exc.status
    msg = exc.message
    if not msg and dbg and exc.__cause__: msg = str(exc.__cause__)
  else:
    status = INTERNAL_SERVER_ERROR
    msg = repr(exc) if dbg else ''
  response_bytes = http_status_versioned_response_bytes[status]
  if msg:
    response_bytes += b': ' + msg.encode('latin1', 'replace')
  return response_bytes + b'\r\n'


def response_header_date_value(timestamp:float|None=None) -> bytes:
  return format_date_time(timestamp).encode('latin1')


def response_header_date_line(timestamp:float|None=None) -> bytes:
  return b'Date: ' + format_date_time(timestamp).encode('latin1') + b'\r\n'


def may_send_body(method:HTTPMethod, status:HTTPStatus) -> bool:
  '''
  Return True if the body of the response should be sent.
  See:
  * https://www.rfc-editor.org/rfc/rfc7230#section-3.3
  * https://www.rfc-editor.org/rfc/rfc7231#section-6.3.6
  '''
  if method == HTTPMethod.HEAD: return False
  if method == HTTPMethod.CONNECT and 200 <= status < 300: return False # Successful connect responses.
  if method.is_informational: return False # type: ignore[union-attr]
  if status in non_body_statuses: return False
  return True


response_connection_close_line = b'Connection: close\r\n'
