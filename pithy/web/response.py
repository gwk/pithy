# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from html import escape as html_escape
from http import HTTPStatus
from io import BufferedReader
from os import fstat as os_fstat
from typing import Self

from ..http import format_header_date, may_send_body, non_body_statuses
from ..markup import Mu
from .errors import ResponseError
from .headers import add_header_item, ResponseHeadersDict


ResponseBody = str|bytes|bytearray|BufferedReader|Mu|None

BinaryResponseBody = bytes|bytearray|BufferedReader|None
# TODO: support iterable[bytes]?


class Response:
  '''
  Response encapsulates all of the information needed to respond to an HTTP request:
  * status: The HTTP status code (default: OK).
  * headers: a dictionary of HTTP headers.
  * body: The response body.

  Additionally, there are keyword parameters for some common headers:
  * media_type: The Content-Type header.
  * last_modified: The Last-Modified header.

  'Content-Length' is automatically set based on the status and body.

  The constructor checks that the body is appropriate for the status code.
  '''

  status:HTTPStatus
  headers:ResponseHeadersDict
  body:BinaryResponseBody


  def __init__(self, status:HTTPStatus=HTTPStatus.OK, *, headers:ResponseHeadersDict|None=None,
   body:ResponseBody|None=None, media_type:str='', last_modified:float=0.0) -> None:

    self.status = status
    self.headers = {} if headers is None else headers

    if body is not None:
      if 100 <= status < 200 or status in non_body_statuses:
        # These status codes must not have a body.
        # 204, 304: https://www.rfc-editor.org/rfc/rfc7230#section-3.3
        # 205: https://www.rfc-editor.org/rfc/rfc7231#section-6.3.6
        # 304: https://www.rfc-editor.org/rfc/rfc7232#section-4.1
        raise ValueError(f'{status} response must not have a body.')

    if 'date' not in self.headers and status != HTTPStatus.CONTINUE and status != HTTPStatus.SWITCHING_PROTOCOLS:
      self.headers['date'] = format_header_date()

    # Convert body to bytes if necessary.
    if isinstance(body, str):
      binary_body:BinaryResponseBody = body.encode('utf-8', errors='replace')
    elif isinstance(body, Mu):
      binary_body = bytes(body)
    else:
      binary_body = body
    self.body = binary_body

    if isinstance(binary_body, BufferedReader):
      content_length = content_length_for_file(binary_body)
    elif binary_body is not None: # Non-file body.
      content_length = len(binary_body)
    else:
      content_length = 0

    assert 'content-length' not in self.headers
    self.headers['content-length'] = content_length

    if media_type:
      assert 'content-type' not in self.headers
      self.headers['content-type'] = media_type

    if last_modified:
      assert 'last-modified' not in self.headers
      self.headers['last-modified'] = last_modified


  @classmethod
  def from_error(self, error:ResponseError, method:str) -> Self:
    '''
    Create the response for an error.
    '''
    body:ResponseBody|None = None
    media_type = ''
    if may_send_body(method, self.status):
      body = error_html_format.format(code=self.status.value, reason=html_escape(error.reason or error.status.phrase, quote=False))
      #^ HTML-escape the reason to prevent Cross Site Scripting attacks (see cpython bug #1100201).
      media_type = error_media_type
    return self(error.status, headers=error.headers, body=body, media_type=media_type)




  def headers_bytes_list(self) -> list[tuple[bytes,bytes]]:
    return [(k.encode('ascii'), (', '.join(str(a) for a in v) if isinstance(v, list) else str(v)).encode('latin1'))
      for (k, v) in self.headers.items()]


  def set_connection_close_header(self) -> None:
    self.headers['connection'] = 'close'


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
  <h1>Error: {code}</h1>
  <p>{reason}.</p>
</body>
</html>
'''


html_media_type = 'text/html;charset=utf-8'
error_media_type = html_media_type
