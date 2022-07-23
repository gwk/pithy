# Derived from cpython/Lib/http/server.py.
# Changes dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import mimetypes
import sys
import time
from cgi import parse_header as cgi_parse_header, parse_multipart
from email.utils import formatdate as format_email_date
from html import escape as html_escape
from http import HTTPStatus
from http.client import HTTPException, HTTPMessage, parse_headers
from io import BufferedIOBase, BufferedReader
from os import environ, fstat as os_fstat
from shutil import copyfileobj
from socket import getfqdn as get_fully_qualified_domain_name, socket
from socketserver import StreamRequestHandler, ThreadingTCPServer
from sys import exc_info
from traceback import print_exception
from typing import ByteString, Optional, Tuple, Type, Union, cast
from urllib.parse import (SplitResult as Url, quote as url_quote, unquote as url_unquote, urlsplit as url_split,
  urlunsplit as url_join, parse_qs)

from ..fs import is_dir, scan_dir, norm_path, path_exists
from ..io import errL, errSL
from ..path import path_ext, path_join


'''
This server implementation is derived from the stdlib http.server.
It was originally pulled from CPython 3.7.
It has since been updated to CPython 3.10.0; the last reviewed commit is 058f9b27d3.
Note that not all changes have been ported.
Since then it has changed substantially.
'''


__version__ = '0'

_default_error_html_format = '''\
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Error: {code}</title>
</head>
<body>
  <h1>Error: {code} - {reason}</h1>
</body>
</html>
'''

_default_error_content_type = html_content_type = b'text/html;charset=utf-8'


class UnrecoverableServerError(Exception):
  'An error occurred for which the server cannot recover.'


class HttpContentError(Exception):
  '''
  An error that causes the current request handler to return the specified HTTP status code.
  Implementations of get_content can raise this as an alternative to returning a Content object.
  '''
  def __init__(self, status:HTTPStatus, reason:str='', headers:Optional[dict[bytes,ByteString]]=None):
    self.status = status
    self.reason = reason
    self.headers = headers
    super().__init__(f'{status} - {reason}')


ContentBody = Union[None,str,bytes,bytearray,BufferedReader]
BinaryContentBody = Union[None,bytes,bytearray,BufferedReader]
#^ Note: normally we would use the abstract BinaryIO type
#  but mypy does not understand the Union difference when test the concrete type.

class HttpContent:
  '''
  Implementations of get_content return instances of this type for each request.
  '''
  def __init__(self, body:ContentBody, content_type:bytes=b'', last_modified:float=0.0) -> None:
    self.body:BinaryContentBody = body.encode('utf8', errors='replace') if isinstance(body, str) else body
    self.content_type = content_type
    self.last_modified = last_modified


class HttpServer(ThreadingTCPServer):
  '''
  HttpServer is an HTTP/1.1 server.
  In order to serve HTTP 1.1, the class must inherit from socketserver.ThreadingMixIn to function correctly.
  '''

  daemon_threads = True # Same as http.server.ThreadingHTTPServer.

  allow_reuse_address = True # See cpython/Lib/socketserver.py.
  #^ Controls whether `self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)` is called.

  unrecoverable_exception_types: Tuple[Type, ...] = (
    AttributeError,
    ImportError,
    MemoryError,
    NameError,
    SyntaxError,
  )


  def __init__(self, server_address:Tuple[str,int], RequestHandlerClass:Type['HttpRequestHandler'],
   bind_and_activate=True, local_dir:str='', prevent_client_caching:bool=False, assume_local_html:bool=False) -> None:

    self.dbg = environ.get('DEBUG') is not None
    self.local_dir = local_dir.rstrip('/')
    self.prevent_client_caching = prevent_client_caching
    self.assume_local_html = assume_local_html

    super().__init__(server_address=server_address, RequestHandlerClass=RequestHandlerClass,
      bind_and_activate=bind_and_activate)


  def server_bind(self) -> None:
    '''Override TCP.server_bind to store the server name.'''
    super().server_bind()
    host, port = self.server_address[:2]
    self.server_name = get_fully_qualified_domain_name(host)
    self.server_port = port


  def handle_error(self, request:Union[socket, Tuple[bytes,socket]], client_address:Union[tuple[str,int],str]) -> None:
    '''
    Override BaseServer.handle_error to fail fast for unrecoverable errors.
    '''
    errL()
    errSL('Exception while processing request from client:', client_address)
    e_type, exc, traceback = exc_info()
    if isinstance(exc, self.unrecoverable_exception_types):
      raise UnrecoverableServerError from exc
    else:
      print_exception(e_type, exc, traceback)
      errL('-'*40)


class HttpRequestHandler(StreamRequestHandler):

  server: HttpServer

  python_version = 'Python/{}.{}.{}'.format(*sys.version_info[:3])

  server_version = f'pithy.http.server/{__version__} {python_version}'.encode('latin1')
  #^ The format is multiple whitespace-separated strings, where each string is of the form name[/version].

  error_html_format = _default_error_html_format
  error_content_type = _default_error_content_type

  protocol_version = 'HTTP/1.1'

  if not mimetypes.inited: mimetypes.init()
  ext_mime_types = { ext : mime_type.encode('latin1') for (ext, mime_type) in mimetypes.types_map.items() }
  ext_mime_types.update({
    '': b'text/plain', # Default.
    '.bz2': b'application/x-bzip2',
    '.gz': b'application/gzip',
    '.sh': b'text/plain', # Show source instead of prompting download.
    '.xz': b'application/x-xz',
    '.z': b'application/octet-stream',
    })


  request_line_bytes: bytes
  request_line: str
  command: str
  target: str
  url: Url
  headers: Optional[HTTPMessage]
  close_connection: bool
  sent_response: bool

  def __init__(self, request:Union[socket, Tuple[bytes,socket]], client_address:tuple[str,int], server:HttpServer) -> None:
    self.reset()
    self.reuse_count = 0
    super().__init__(request=request, client_address=client_address, server=server)


  def reset(self) -> None:
    self.request_line_bytes = b''
    self.request_line = ''
    self.command = ''
    self.target = ''
    self.url = url_split('')
    self.headers = None # The request headers.
    self.close_connection = True
    self.sent_response = False

  def handle(self) -> None:
    '''
    Override point provided by BaseRequestHandler.
    Handle multiple requests if necessary.
    '''
    self.handle_one_request()
    while not self.close_connection:
      self.reset()
      self.reuse_count += 1
      self.handle_one_request()


  def handle_one_request(self) -> None:
    '''
    Handle a single HTTP request.
    '''
    try:
      # Parse request.
      self.request_line_bytes = self.rfile.readline(65537)
      if not self.request_line_bytes:
        return
      if len(self.request_line_bytes) > 65536:
        self.send_error(HTTPStatus.REQUEST_URI_TOO_LONG, headers={})
        return
      if error_args := self.parse_request():
        status, reason = error_args
        self.send_error(status=status, reason=reason, headers={})
        return
      assert self.headers is not None
      # Handle 'Expect'.
      expect = self.headers.get('Expect', '').lower()
      if expect == '100-continue':
        if not self.handle_expect_100(): return
      # Determine method and dispatch.
      method_name = 'handle_http_' + self.command
      method = getattr(self, method_name, None)
      if not method:
        self.send_error(HTTPStatus.NOT_IMPLEMENTED, headers={}, reason=f'Unsupported method: {self.command!r}')
        return
      method()
      self.wfile.flush() # Send the response if not already done.
    except TimeoutError as e:
      # Either a read or a write timed out. Discard this connection.
      self.log_error(f'Request timed out: {e}')
      self.close_connection = True


  def parse_request(self) -> Optional[tuple[HTTPStatus,str]]:
    self.request_line = request_line = str(self.request_line_bytes, 'latin1').rstrip('\r\n')
    words = request_line.split(' ')
    if not words:
      return (HTTPStatus.BAD_REQUEST, 'Empty request line')
    if len(words) != 3:
      return (HTTPStatus.BAD_REQUEST, f'Bad request syntax: {request_line!r}')
    command, target, version = words
    try:
      if not version.startswith('HTTP/'): raise ValueError
      base_version_number = version.split('/', 1)[1]
      version_numbers = base_version_number.split('.')
      # RFC 2145 section 3.1 says:
      # * there can be only one '.';
      # * major and minor numbers MUST be treated as separate integers;
      # * HTTP/2.4 is a lower version than HTTP/2.13, which in turn is lower than HTTP/12.3;
      # * Leading zeros MUST be ignored by recipients.
      if len(version_numbers) != 2: raise ValueError
      version_number = (int(version_numbers[0]), int(version_numbers[1]))
    except (ValueError, IndexError):
      return (HTTPStatus.BAD_REQUEST, f'Bad request version: {version!r}')
    if version_number < (1, 1) or version_number >= (2, 0):
      return (HTTPStatus.HTTP_VERSION_NOT_SUPPORTED, f'Unsupported HTTP version: {version_number}')

    if command not in http_commands:
      return (HTTPStatus.BAD_REQUEST, f'Unrecognized HTTP command: {command!r}')

    self.command = command
    self.target = target
    try: self.url = url_split(target)
    except ValueError: pass

    # Parse headers.
    try:
      self.headers = parse_headers(cast(BufferedIOBase, self.rfile), _class=HTTPMessage)
    except HTTPException as exc:
      return (HTTPStatus.REQUEST_HEADER_FIELDS_TOO_LARGE, f'{type(exc)}: {exc}')

    # Respect connection directive.
    conn_type = self.headers.get('Connection', '').lower()
    if 'close' in conn_type:
      self.close_connection = True
    else:
      self.close_connection = False # Keep-alive is the default for HTTP/1.1.
    return None



  def handle_expect_100(self) -> bool:
    '''
    Decide what to do with an "Expect: 100-continue" header.

    If the client is expecting a 100 Continue response,
    we must respond with either a 100 Continue or a final response before waiting for the request body.
    The default is to always respond with a 100 Continue.
    You can behave differently (for example, reject unauthorized requests) by overriding this method.

    This method should either return True (possibly after sending a 100 Continue response)
    or send an error response and return False.
    '''
    self.send_response_and_headers(status=HTTPStatus.CONTINUE, headers={})
    return True


  def send_error(self, status:HTTPStatus, *, reason:str='', headers:dict[bytes,ByteString]) -> None:
    '''
    Send and log an error reply.

    Arguments are:
    * status:  HTTPStatus.
    * reason: a simple optional 1 line reason phrase.
      * ( HTAB / SP / VCHAR / %x80-FF ) (TODO: enforce these character requirements).
      * defaults to short entry matching the response code.
    * message: a detailed message defaults to the long entry matching the response code.

    This sends an error response (so it must be called before any output has been generated),
    logs the error, and finally sends a piece of HTML explaining the error to the user.
    '''
    code = status.value
    self.log_error(f'{code} - {reason}')
    self.close_connection = True

    # Message body is omitted for cases described in:
    #  - RFC7230: 3.3. 1xx, 204 (No Content), 304 (Not Modified).
    #  - RFC7231: 6.3.6. 205 (Reset Content).
    body = None
    if (code >= 200 and code not in (HTTPStatus.NO_CONTENT, HTTPStatus.RESET_CONTENT, HTTPStatus.NOT_MODIFIED)):
      content = self.error_html_format.format(code=code, reason=html_escape(reason or status.phrase, quote=False))
      #^ HTML-escape the reason to prevent Cross Site Scripting attacks (see cpython bug #1100201).
      body = content.encode('UTF-8', 'replace')
      headers[b'Content-Type'] = self.error_content_type
      headers[b'Content-Length'] = str(len(body)).encode('latin1')

    self.send_response_and_headers(status=status, reason=reason, headers=headers)
    if self.command != 'HEAD' and body:
      self.wfile.write(body)


  def send_response_and_headers(self, status:HTTPStatus, headers:dict[bytes,ByteString], reason:str='') -> None:
    '''
    Send the response line and headers to the client.
    Adds cache control headers if `server.prevent_client_caching` is set.
    Adds a `Connection: close` header if `close_connection` is set.
    Sets `sent_response` to ensure that this method is only called once.
    '''
    reason = reason or status.phrase
    self.log_message(f'{status.value} {reason} {self.request_line!r}')

    assert not self.sent_response
    self.sent_response = True
    if status != HTTPStatus.CONTINUE:
      # These standard headers are excluded from the 100-continue response because that appears to be the way the python stddlib server worked.
      headers[b'Server'] = self.server_version
      headers[b'Date'] = self.format_header_date()
    if self.server.prevent_client_caching:
      headers.setdefault(b'Cache-Control', b'no-cache, no-store, must-revalidate')
      headers.setdefault(b'Pragma', b'no-cache')
      headers.setdefault(b'Expires', b'0')
    if self.close_connection:
      headers[b'Connection'] = b'close'

    buffer = bytearray(f'{self.protocol_version} {status.value} {reason}\r\n'.encode('latin1'))
    for k, v in headers.items():
      buffer.extend(k)
      buffer.extend(b': ')
      assert isinstance(v, (bytes, bytearray, memoryview)), v
      buffer.extend(v)
      buffer.extend(b'\r\n')
    buffer.extend(b'\r\n')
    self.wfile.write(buffer)

    if self.server.dbg:
      response = buffer.decode('latin1', errors='replace')
      for line in response.splitlines(keepends=True):
        print('  DBG:', repr(line))
      print()


  def handle_http_GET(self) -> None:
    '''Serve a GET request.'''
    body:BinaryContentBody = self.send_head()
    if isinstance(body, BufferedReader):
      try: copyfileobj(body, self.wfile)
      finally: body.close()
    elif body:
      self.wfile.write(body)


  def handle_http_HEAD(self) -> None:
    '''Serve a HEAD request.'''
    body = self.send_head()
    if isinstance(body, BufferedReader):
      body.close()


  def send_head(self) -> BinaryContentBody:
    'Send the head of the response and return an optional body object.'
    try: content = self.get_content()
    except HttpContentError as e:
      headers = e.headers if e.headers is not None else {}
      self.send_error(status=e.status, reason=e.reason, headers=headers)
      return None

    if isinstance(content.body, BufferedReader):
      fd = content.body.fileno()
      stat = os_fstat(fd)
      content_length = stat[6]
    elif content.body:
      content_length = len(content.body)
    else:
      content_length = 0
    headers = {
      b'Content-Type' : content.content_type,
      b'Content-Length' : str(content_length).encode('latin1'),
    }
    self.send_response_and_headers(HTTPStatus.OK, headers=headers)
    return content.body


  def get_content(self) -> HttpContent:
    '''Override point for subclasses to return HttpContent for GET and HEAD requests.'''
    raise HttpContentError(status=HTTPStatus.NOT_FOUND)


  def handle_http_POST(self) -> None:
    '''Serve a POST request.'''
    assert self.headers is not None

    try: content_length = int(self.headers.get('Content-Length', '0'))
    except ValueError:
      return self.send_error(HTTPStatus.BAD_REQUEST, reason='Invalid Content-Length header.', headers={})

    # TODO: before parsing anything, validate that we want to handle this request.

    content_type_val = self.headers.get('Content-Type', '')
    content_type, pdict = cgi_parse_header(content_type_val)

    if content_type == 'application/x-www-form-urlencoded':
      try:
        body = self.rfile.read(content_length)
        text = body.decode()
        content = parse_qs(text)
      except Exception as exc:
        return self.send_error(HTTPStatus.BAD_REQUEST, reason=f'Failed to read request body: {type(exc)}: {exc}', headers={})

    elif content_type == 'multipart/form-data':
      try:
        body = self.rfile.read(content_length)
        content = parse_multipart(self.rfile, pdict=pdict) # type: ignore # TODO: fix or explain this type error.
      except Exception as exc:
        return self.send_error(HTTPStatus.BAD_REQUEST, reason=f'Failed to read request body: {type(exc)}: {exc}', headers={})

    else:
      return self.send_error(HTTPStatus.BAD_REQUEST, reason=f'Unsupported Content-Type: {content_type!r}', headers={})

    try: response = self.post_content(content=content)
    except HttpContentError as e:
      headers = e.headers if e.headers is not None else {}
      self.send_error(status=e.status, reason=e.reason, headers=headers)
      return

    if isinstance(response.body, BufferedReader):
      fd = response.body.fileno()
      stat = os_fstat(fd)
      resp_content_length = stat[6]
    elif response.body:
      resp_content_length = len(response.body)
    else:
      resp_content_length = 0
    resp_headers:dict[bytes,ByteString] = {
      b'Content-Type' : response.content_type,
      b'Content-Length' : str(resp_content_length).encode('latin1'),
    }
    self.send_response_and_headers(HTTPStatus.OK, headers=resp_headers)

    if isinstance(response.body, BufferedReader):
      try: copyfileobj(response.body, self.wfile)
      finally: response.body.close()
    elif response.body:
      self.wfile.write(response.body)


  def post_content(self, content:dict[str,list[str]]) -> HttpContent:
    '''Override point for subclasses to return HttpContent for a POST request.'''
    errL('Unhandled POST request:', content)
    raise HttpContentError(status=HTTPStatus.NOT_FOUND)


  def get_content_from_local_fs(self, local_path:Optional[str]=None) -> HttpContent:
    '''
    Return the content of a local file or a directory listing.
    '''
    if local_path is None:
      local_path = self.compute_local_path()

    if not local_path: raise ValueError(local_path) # Should never end up with an empty string.

    if is_dir(local_path, follow=True):
      if not local_path.endswith('/'): # Redirect browser to path with slash (same behavior as Apache).
        url = self.url
        if url is None: raise HttpContentError(status=HTTPStatus.NOT_FOUND)
        new_url = url_join(url._replace(path=url.path+'/'))
        raise HttpContentError(status=HTTPStatus.MOVED_PERMANENTLY, headers={b'Location':new_url.encode('latin1')})
      index_path = path_join(local_path, 'index.html')
      if path_exists(index_path, follow=False):
        local_path = index_path
      else:
        return self.list_directory(local_path)

    try: f = open(local_path, 'rb')
    except (FileNotFoundError, PermissionError): raise HttpContentError(status=HTTPStatus.NOT_FOUND)

    assert isinstance(f, BufferedReader)
    return self.transform_file_from_local_fs(file=f, local_path=local_path)


  def transform_file_from_local_fs(self, file:BufferedReader, local_path:str) -> HttpContent:
    '''
    Override point to transform the content of a local file. The base implementation returns the file handle unaltered.
    '''
    return HttpContent(body=file, content_type=self.guess_mime_type(local_path))


  def compute_logical_path(self, target:Optional[str]=None) -> str:
    '''
    Compute logical path from the request target (URL string).
    The logical path is normalized but not sanitized.
    In particular it can still contain '..', so is not safe to use without further checking.
    `compute_local_path` will sanitize the path.
    '''
    if target is None:
      p = self.url.path
    else:
      p = url_split(target).path
    if not p.startswith('/'): raise ValueError(p)
    trailing_slash = '/' if (p != '/' and p.endswith('/')) else ''
    p = url_unquote(p)
    p = norm_path(p)
    if p != '/' and p.endswith('/'): raise ValueError(p) # Should be guaranteed by norm_path.
    return p + trailing_slash


  def compute_local_path(self, logical_path:Optional[str]=None) -> str:
    'Compute local_path from a logical path.'

    local_dir = self.server.local_dir
    if not local_dir: raise HttpContentError(HTTPStatus.NOT_FOUND) # Local FS access is not configured.
    if local_dir.endswith('/'): raise ValueError(local_dir)

    if logical_path is None: logical_path = self.compute_logical_path()
    logical_path = self.transform_logical_path_for_local(logical_path)
    if not logical_path.startswith('/'): raise ValueError(logical_path)
    if '..' in logical_path: raise HttpContentError(HTTPStatus.FORBIDDEN)

    if self.server.assume_local_html and not logical_path.endswith('/') and not path_ext(logical_path):
      logical_path += '.html'

    return local_dir + logical_path


  def transform_logical_path_for_local(self, logical_path:str) -> str:
    '''
    Called by compute_logical_path; override point for subclasses to transform the normalized logical path.
    The default implementation returns the logical path unchanged.
    '''
    return logical_path


  def list_directory(self, local_path:str) -> HttpContent:
    '''
    Produce a directory listing html page (absent index.html).
    '''
    try: listing = scan_dir(local_path)
    except OSError as e:
      errL('Failed to list directory:', local_path, e)
      raise HttpContentError(status=HTTPStatus.NOT_FOUND)
    listing.sort(key=lambda e: cast(str, e.name.lower()))

    try: display_path = url_unquote(self.url.path, errors='replace')
    except UnicodeDecodeError:
      display_path = url_unquote(self.url.path)

    title = html_escape(display_path, quote=False)

    r = []
    r.append('<!DOCTYPE html>\n<html>')
    r.append(f'<head>\n<meta charset="utf-8" />\n<title>{title}</title>\n</head>')
    r.append(f'<body>\n<h1>{title}</h1>')
    r.append('<hr>\n<ul>')
    for entry in listing:
      n = entry.name + ('/' if entry.is_dir(follow_symlinks=True) else '')
      link_href = url_quote(n, errors='replace')
      link_text = html_escape(n, quote=False)
      r.append(f'<li><a href="{link_href}">{link_text}</a></li>')
    r.append('</ul>\n<hr>\n</body>\n</html>\n')
    body = '\n'.join(r).encode(errors='replace')
    return HttpContent(body=body, content_type=html_content_type)


  def fake_favicon(self) -> None:
    'This was a hack to prevent favicon request errors from showing up in the logs.'
    if self.target == '/favicon.ico': # TODO: send actual favicon if it exists.
      self.response_status = HTTPStatus.OK
      headers:dict[bytes,ByteString] = {
        b'Content-type': b'image/x-icon',
        b'Content-Length': b'0'
      }
      self.send_response_and_headers(HTTPStatus.OK, headers=headers)
      return None


  def guess_mime_type(self, path:str) -> bytes:
    'Guess the mime type for a file path.'
    ext = path_ext(path).lower()
    try: return self.ext_mime_types[ext]
    except KeyError: return self.ext_mime_types['']


  def log_message(self, msg:str) -> None:
    'Base logging function called by all others.'
    errL(f'{self.format_log_date()}  {self.client_address_string()}: {msg}')


  def log_error(self, msg:str) -> None:
    '''Log an error. Called when a request cannot be fulfilled. By default it passes the message on to log_message().'''
    self.log_message(msg)


  def format_log_date(self, timestamp:float=None) -> str:
    'Format the current time for logging.'
    if timestamp is None: timestamp = time.time()
    ts = time.localtime(timestamp)
    y, m, d, hh, mm, ss, wd, yd = ts[:8]
    return f'{y:04}-{m:02}-{d:02} {hh:02}:{mm:02}:{ss:02}.{timestamp:.03f}'


  def format_header_date(self, timestamp:float=None) -> bytes:
    'Format `timestamp` or now for an HTTP header value.'
    return format_email_date(time.time() if timestamp is None else timestamp, usegmt=True).encode('latin1')


  def client_address_string(self) -> str:
    '''Return the client address.'''
    return self.client_address[0] # type: ignore


http_commands = frozenset({
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
