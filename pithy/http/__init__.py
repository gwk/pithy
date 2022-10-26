# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import time
from email.utils import formatdate as format_email_date
from http import HTTPStatus


http_status_response_strings = { s : f'{s.value} {s.phrase}'  for s in HTTPStatus }

http_methods = frozenset({
  'CONNECT',
  'DELETE',
  'GET',
  'HEAD',
  'OPTIONS',
  'PATCH',
  'POST',
  'PUT',
  'TRACE',
})


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
  if status in (HTTPStatus.NO_CONTENT, HTTPStatus.RESET_CONTENT, HTTPStatus.NOT_MODIFIED): return False
  #^ Note: RFC 7230 3.3 does not mention 205 RESET CONTENT but RFC 7231 6.3.6 does.
  return True


def format_header_date(timestamp:float|None=None) -> str:
  'Format `timestamp` or now for an HTTP header value.'
  if timestamp is None: timestamp = time.time()
  return format_email_date(timestamp, usegmt=True)
