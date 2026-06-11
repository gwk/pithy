# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from email.utils import formatdate as format_email_date
from http import HTTPStatus
from time import time as unix_epoch_time
from typing import get_args, Literal


http_status_response_strings = { s : f'{s.value} {s.phrase}'  for s in HTTPStatus }

HttpEndpointMethod = Literal['DELETE', 'GET', 'HEAD', 'OPTIONS', 'PATCH', 'POST', 'PUT', 'TRACE']
endpoint_methods:frozenset[str] = frozenset(get_args(HttpEndpointMethod))

HttpMethod = HttpEndpointMethod | Literal['CONNECT']
http_methods = endpoint_methods | {'CONNECT'}


http_method_bytes_to_strs = { m.encode('ascii'): m for m in http_methods }
http_methods_strs_to_bytes = { m: m.encode('ascii') for m in http_methods }


non_body_statuses = (
  HTTPStatus.NO_CONTENT,
  HTTPStatus.RESET_CONTENT, # Note: RFC 7230 3.3 does not mention 205 RESET CONTENT but RFC 7231 6.3.6 does.
  HTTPStatus.NOT_MODIFIED,
)


def may_send_body(method:str, status:HTTPStatus) -> bool:
  '''
  Return True if the body of the response should be sent.
  See:
  * https://www.rfc-editor.org/rfc/rfc7230#section-3.3
  * https://www.rfc-editor.org/rfc/rfc7231#section-6.3.6
  '''
  if method == 'HEAD': return False
  if method == 'CONNECT' and 200 <= status < 300: return False # Successful connect responses.
  if 100 <= status < 200: return False # Informational responses.
  if status in non_body_statuses: return False
  return True


def format_header_date(timestamp:float|None=None) -> str:
  'Format `timestamp` or now for an HTTP header value.'
  if timestamp is None: timestamp = unix_epoch_time()
  return format_email_date(timestamp, usegmt=True)
