# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import sys
from cgi import parse_header as cgi_parse_header, parse_multipart
from dataclasses import dataclass
from email.utils import formatdate as format_email_date
from html import escape as html_escape
from http import HTTPStatus
from http.client import HTTPMessage
from io import BufferedReader
from os import fstat as os_fstat
from typing import Any, BinaryIO, Optional, TextIO, Union
from urllib.parse import parse_qs, unquote as url_unquote, urlsplit as url_split

from ..http import http_methods, may_send_body
from ..markup import Mu
from ..path import norm_path, path_ext
from ..util import lazy_property


pithy_web_static_dir_path = sys.modules[__name__].__path__[0] + '/static'


ResponseBody = Union[None,str,bytes,bytearray,BufferedReader,Mu]

BinaryResponseBody = Union[None,bytes,bytearray,BufferedReader]
#^ Note: normally we would use the abstract BinaryIO type
#  but mypy does not understand the difference between the unions when testing the runtime file type.
# TODO: support iterable[bytes]?


@dataclass
class Request:
  method:str
  scheme:str
  host:str
  port:int
  path:str
  query:str
  body_file:BinaryIO
  err:TextIO
  is_multiprocess:bool
  is_multithread:bool
  headers:dict[str,str]
  content_length:int = -1


  def __post_init__(self) -> None:
    if self.method not in http_methods: raise BadRequest('Unrecognized method.')
    if self.content_length < 0:
      try: self.content_length = int(self.headers.get('Content-Length', 0))
      except KeyError: pass
      except ValueError: raise BadRequest('Non-integer Content-Length header.')


  @lazy_property
  def path_parts(self) -> list[str]:
    assert self.path.startswith('/')
    parts = self.path.split('/')
    if not parts[-1]: del parts[-1]
    del parts[0]
    return parts


  @lazy_property
  def body_bytes(self) -> bytes:
    try: return self.body_file.read(self.content_length) if self.content_length else b''
    except Exception as exc: raise BadRequest('Failed to read request body') from exc


  @lazy_property
  def post_params_multi(self) -> dict[str,list[str]]:
    '''
    Parse the request body as POST.
    In the case of multipart/form-data, this consumes the request input file,
    due to the stdlib implementation of parse_multipart.
    '''

    media_type_val = self.headers.get('Content-Type', '')
    try: media_type, pdict = cgi_parse_header(media_type_val)
    except Exception as exc: raise BadRequest(f'Invalid Content-Type header: {media_type_val!r}') from exc

    if media_type == 'application/x-www-form-urlencoded':
      body = self.body_bytes
      try: text = body.decode()
      except Exception as exc: raise BadRequest('Failed to decode urlencoded form.') from exc
      try: return parse_qs(text)
      except Exception as exc: raise BadRequest('Failed to read request body.') from exc

    elif media_type == 'multipart/form-data':
      # TODO: use cgi.FieldStorage instead?
      try: content = parse_multipart(self.body_file, pdict=pdict) # type: ignore[arg-type] # TODO: fix or explain this type error.
      except Exception as exc: raise BadRequest('Failed to read/parse POST multipart/form-data request body') from exc

    else: raise BadRequest(f'Unsupported Content-Type: {media_type!r}')

    return content


  @lazy_property
  def post_params_single(self) -> dict[str,str]:
    params_multi = self.post_params_multi
    single = {}
    for k, vs in params_multi.items():
      if len(vs) != 1: raise BadRequest(f'POST parameter {k!r} has multiple values.')
      single[k] = vs[0]
    return single


  def allow_methods(self, *methods:str) -> None:
    '''
    If the current request method is one of the specified methods, return. Otherwise respond with 405 Method Not Allowed.
    This should be called by handle_request to enforce the allowed methods.
    '''
    if self.method not in methods: raise ResponseError(status=HTTPStatus.METHOD_NOT_ALLOWED)



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
  headers:dict[str,float|int|str]
  body:BinaryResponseBody


  def __init__(self, status:HTTPStatus=HTTPStatus.OK, *, headers:dict[str,float|int|str]|None=None, body:ResponseBody|None=None,
   media_type:str='', last_modified:float=0.0) -> None:

    self.status = status
    self.headers = {} if headers is None else headers

    if body is not None:
      if 100 <= status < 200 or status in (HTTPStatus.NO_CONTENT, HTTPStatus.RESET_CONTENT, HTTPStatus.NOT_MODIFIED):
        # These status codes must not have a body.
        # 204, 304: https://www.rfc-editor.org/rfc/rfc7230#section-3.3
        # 205: https://www.rfc-editor.org/rfc/rfc7231#section-6.3.6
        # 304: https://www.rfc-editor.org/rfc/rfc7232#section-4.1
        raise ValueError(f'{status} response must not have a body.')

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
    self.headers['Content-Length'] = content_length

    if media_type:
      self.headers['Content-Type'] = media_type
    if last_modified:
      self.headers['Last-Modified'] = last_modified


  def headers_list(self) -> list[tuple[str,str]]:
    return [(k, str(v)) for (k,v) in self.headers.items()]


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

  def __init__(self, status:HTTPStatus, reason:str='', headers:dict[str,float|int|str]|None=None):
    self.status = status
    self.reason = reason
    self.headers = headers
    super().__init__(f'{status}: {reason}')


  def response(self, method:str) -> Response:
    '''
    Create the response for an error.
    '''
    body:Optional[ResponseBody] = None
    media_type = ''
    if may_send_body(method, self.status):
      body = error_html_format.format(code=self.status.value, reason=html_escape(self.reason or self.status.phrase, quote=False))
      #^ HTML-escape the reason to prevent Cross Site Scripting attacks (see cpython bug #1100201).
      media_type = error_media_type
    return Response(self.status, headers=self.headers, body=body, media_type=media_type)


ResponseNotFound = ResponseError(HTTPStatus.NOT_FOUND)
ResponseNotImplemented = ResponseError(HTTPStatus.NOT_IMPLEMENTED)


def BadRequest(reason:str='') -> ResponseError:
  return ResponseError(HTTPStatus.BAD_REQUEST, reason=reason)


def content_length_for_file(file:BufferedReader) -> int:
  '''Get a file's size in bytes using its file descriptor and fstat.'''
  fd = file.fileno()
  stat = os_fstat(fd)
  return stat.st_size


def norm_url_path(url:str) -> str:
  '''
  Compute a normalized path from the argument url.
  The path is not safe to use as is: it can still contain '..'.
  `compute_local_path` will sanitize the path.
  '''
  path = url_split(url).path
  if not path.startswith('/'): raise ValueError(path)
  trailing_slash = '/' if (path != '/' and path.endswith('/')) else ''
  path = url_unquote(path)
  path = norm_path(path)
  if path != '/' and path.endswith('/'): raise ValueError(path) # Should be guaranteed by norm_path.
  return path + trailing_slash


def compute_local_path(*, local_dir:str, norm_path:str, map_bare_names_to_html:bool) -> str:
  '''
  Compute local_path from a normalized url path (result of `norm_url_path`).
  If `map_bare_names_to_html` is True, then a path without a file extension has '.html' appended.
  '''

  if not local_dir or local_dir.endswith('/'): raise ValueError(local_dir)

  if not norm_path.startswith('/'): raise ValueError(norm_path)
  if '..' in norm_path: raise ResponseError(HTTPStatus.FORBIDDEN)

  if map_bare_names_to_html and not norm_path.endswith('/') and not path_ext(norm_path):
    norm_path += '.html'

  return local_dir + norm_path
