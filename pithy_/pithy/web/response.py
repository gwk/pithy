# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from dataclasses import dataclass
from html import escape as html_escape
from http import HTTPStatus
from io import BufferedReader
from os import fstat as os_fstat
from typing import Self

from pithy.json import render_json

from ..http import format_header_date, may_send_body, non_body_statuses
from ..markup import Mu
from .errors import ResponseError
from .headers import add_header_item, ResponseHeadersDict


ResponseBody = str|bytes|bytearray|BufferedReader|Mu|None

BinaryResponseBody = bytes|bytearray|BufferedReader|None
# TODO: support iterable[bytes]?


@dataclass(slots=True)
class Response():
  '''
  `Response` encapsulates all of the information needed to respond to an HTTP request:
  * status: The HTTP status code (default: OK).
  * headers: a dictionary of HTTP headers. The dictionary will be copied by the constructor.
  * body: The response body.

  Additionally, there are keyword parameters for some common headers:
  * media_type: The Content-Type header.
  * last_modified: The Last-Modified header.

  'Content-Length' is automatically set based on the status and body.

  The constructor checks that the body is appropriate for the status code.
  '''

  status:HTTPStatus
  reason:str
  headers:ResponseHeadersDict
  body:BinaryResponseBody

  def __init__(self, status:HTTPStatus=HTTPStatus.OK, *, reason:str='', headers:ResponseHeadersDict|None=None,
   body:ResponseBody|None=None, media_type:str='', last_modified:float=0.0) -> None:

    self.status = status
    self.reason = reason

    if headers is None: headers = {}
    else:
      headers = headers.copy()
      for k in headers.keys():
        if not k.islower(): raise ValueError(f'Response header name must be lowercase: {k!r}.')

    self.headers = headers

    if media_type:
      assert 'content-type' not in headers
      headers['content-type'] = media_type

    if last_modified:
      assert 'last-modified' not in headers
      headers['last-modified'] = format_header_date(last_modified)

    if body is not None:
      if 100 <= status < 200 or status in non_body_statuses:
        # These status codes must not have a body.
        # 204, 304: https://www.rfc-editor.org/rfc/rfc7230#section-3.3
        # 205: https://www.rfc-editor.org/rfc/rfc7231#section-6.3.6
        # 304: https://www.rfc-editor.org/rfc/rfc7232#section-4.1
        raise ValueError(f'{status} response must not have a body.')

    # Convert body to bytes if necessary.
    if isinstance(body, str):
      binary_body:BinaryResponseBody = body.encode('utf-8')
    elif isinstance(body, Mu):
      binary_body = bytes(body)
    else:
      binary_body = body
    self.body = binary_body

    if isinstance(self.body, BufferedReader):
      content_length = content_length_for_file(self.body)
    elif self.body is not None: # Non-file body.
      content_length = len(self.body)
    else:
      content_length = 0

    assert 'content-length' not in headers
    headers['content-length'] = content_length

    assert 'connection' not in headers


  def headers_bytes_list(self) -> list[tuple[bytes,bytes]]:
    return [(k.encode('ascii'), (', '.join(str(a) for a in v) if isinstance(v, list) else str(v)).encode('latin1'))
      for (k, v) in self.headers.items()]


  def set_connection_close(self) -> Self:
    self.headers['connection'] = 'close'
    return self


  @classmethod
  def from_error(cls, error:ResponseError, method:str) -> Self:
    '''
    Create the response for an error.
    '''
    body:ResponseBody|None = None
    media_type = ''
    if may_send_body(method, error.status):
      body = error_html_format.format(code=error.status.value,
        reason=html_escape(error.reason or error.status.phrase, quote=False))
      #^ HTML-escape the reason to prevent Cross Site Scripting attacks (see cpython bug #1100201).
      media_type = error_media_type
    return cls(error.status, reason=error.reason, headers=error.headers, body=body, media_type=media_type)


  def set_no_cache_headers(self) -> None:
    'Should only be called for HEAD, GET, and POST responses.'
    add_header_item(self.headers, 'Cache-Control', 'no-cache, no-store, must-revalidate')
    add_header_item(self.headers, 'Pragma', 'no-cache')
    add_header_item(self.headers, 'Expires', '0')



def content_length_for_file(file:BufferedReader) -> int:
  '''
  Get the number of bytes remaining in a file using fstat and tell.
  fstat gives the total file size; subtracting the current position gives the bytes remaining to be read.
  This is correct even if the file was opened at a non-zero offset or partially consumed before being passed here.
  '''
  fd = file.fileno()
  stat = os_fstat(fd)
  return stat.st_size - file.tell()



error_html_format = '''\
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Error: {code}</title>
</head>
<body>
  <p>{code}: {reason}.</p>
</body>
</html>
'''


html_media_type = 'text/html;charset=utf-8'
error_media_type = html_media_type


class HtmlResponse(Response):
  'A Response subclass for HTML responses.'

  def __init__(self, body:Mu|str, *, status:HTTPStatus=HTTPStatus.OK, reason:str='', headers:ResponseHeadersDict|None=None,
   last_modified:float=0.0) -> None:
    super().__init__(status=status, reason=reason, headers=headers, body=body, media_type=html_media_type,
     last_modified=last_modified)


class JsonResponse(Response):
  'A Response subclass for JSON responses. The `body` object is serialized to JSON'

  def __init__(self, body:str, *, status:HTTPStatus=HTTPStatus.OK, reason:str='', headers:ResponseHeadersDict|None=None,
   last_modified:float=0.0, prerendered:bool=False) -> None:

    if prerendered:
      if not isinstance(body, str): raise ValueError('prerendered body must be a string.')
      json_body = body
    else:
        json_body = render_json(body)
    super().__init__(status=status, reason=reason, headers=headers, body=json_body, media_type='application/json',
     last_modified=last_modified)


class TextResponse(Response):
  'A Response subclass for plain text responses.'

  def __init__(self, body:str, *, status:HTTPStatus=HTTPStatus.OK, reason:str='', headers:ResponseHeadersDict|None=None,
   last_modified:float=0.0) -> None:
    super().__init__(status=status, reason=reason, headers=headers, body=body, media_type='text/plain;charset=utf-8',
     last_modified=last_modified)
