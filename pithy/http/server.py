# Derived from cpython/Lib/http/server.py.
# Changes dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import mimetypes
import sys
import time
from email.utils import formatdate as format_email_date
from html import escape as html_escape
from http import HTTPStatus
from http.client import HTTPException, HTTPMessage, parse_headers
from io import BufferedReader
from os import environ, fstat as os_fstat
from shutil import copyfileobj
from socket import getfqdn as get_fully_qualified_domain_name
from socketserver import StreamRequestHandler, ThreadingTCPServer
from sys import exc_info
from traceback import print_exception
from typing import ByteString, Optional, Tuple, Type, Union
from urllib.parse import quote as url_quote, unquote as url_unquote, urlsplit as url_split, urlunsplit as url_join

from ..fs import is_dir, list_dir, norm_path, path_exists
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
   bind_and_activate=True) -> None:

    self.dbg = environ.get('DEBUG') is not None

    super().__init__(server_address=server_address, RequestHandlerClass=RequestHandlerClass,
      bind_and_activate=bind_and_activate)


  def server_bind(self) -> None:
    '''Override TCP.server_bind to store the server name.'''
    super().server_bind()
    host, port = self.server_address[:2]
    self.server_name = get_fully_qualified_domain_name(host)
    self.server_port = port


  def handle_error(self, request:bytes, client_address:tuple[str,int]) -> None:
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

  server: HttpServer # Covariant type override of BaseRequestHandler.

  python_version = 'Python/{}.{}.{}'.format(*sys.version_info[:3])

  server_version = f'pithy.http.server/{__version__} {python_version}'.encode('latin1')
  #^ The format is multiple whitespace-separated strings, where each string is of the form name[/version].

  error_html_format = _default_error_html_format
  error_content_type = _default_error_content_type

  prevent_client_caching = False

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
  path: str
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
    self.path = ''
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
    command, path, version = words
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
    self.path = path

    # Parse headers.
    try:
      self.headers = parse_headers(self.rfile, _class=HTTPMessage) # type: ignore
    except HTTPException as exc:
      return (HTTPStatus.REQUEST_HEADER_FIELDS_TOO_LARGE, f'{type(exc)}: {exc}')

    # Respect connection directive.
    conn_type = self.headers.get('Connection', '').lower()
    if 'close' in conn_type:
      self.close_connection = True
    else:
      self.close_connection = False # Keep-alive is the default for HTTP/1.1.
    return None


  def compute_local_path(self) -> Optional[str]:
    'Compute local_path.'
    p = self.path
    # abandon query and fragment parameters.
    p = p.partition('?')[0]
    p = p.partition('#')[0]
    trailing_slash = '/' if p.rstrip().endswith('/') else ''
    p = url_unquote(p)
    p = norm_path(p)
    if '..' in p: return None
    assert p.startswith('/')
    p = p.lstrip('/') # Remove leading slash.
    if not p: p = '.'
    return p + trailing_slash


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
    Adds cache control headers if `prevent_client_caching` is set.
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
    if self.prevent_client_caching:
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
        print(repr(line))
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
    'Send the head of the response and return an optional file object for the body.'
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
    raise HttpContentError(status=HTTPStatus.NOT_FOUND)


  def get_content_from_local_fs(self, local_path:Optional[str]) -> HttpContent:
    '''
    Return the content of a file.
    '''
    if not local_path:
      raise HttpContentError(HTTPStatus.UNAUTHORIZED)

    if is_dir(local_path, follow=True):
      if not local_path.endswith('/'): # Redirect browser to path with slash (same behavior as Apache).
        parts = url_split(self.path)
        new_url = url_join(parts.replace(path=parts.path+'/')) # type: ignore
        raise HttpContentError(status=HTTPStatus.MOVED_PERMANENTLY, headers={b'Location':new_url.encode('latin1')})
      index_path = path_join(local_path, 'index.html')
      if path_exists(index_path, follow=False):
        local_path = index_path
      else:
        return self.list_directory(local_path)

    try: f = open(local_path, 'rb')
    except (FileNotFoundError, PermissionError):
      raise HttpContentError(status=HTTPStatus.NOT_FOUND)
    else:
      assert isinstance(f, BufferedReader)
      return HttpContent(body=f, content_type=self.guess_mime_type(local_path))



  def list_directory(self, path:str) -> HttpContent:
    '''
    Produce a directory listing html page (absent index.html).
    '''
    try: listing = list_dir(path)
    except OSError: raise HttpContentError(status=HTTPStatus.NOT_FOUND)
    listing.sort(key=lambda a: a.lower())

    try: displaypath = url_unquote(self.path, errors='replace')
    except UnicodeDecodeError:
      displaypath = url_unquote(path)

    title = html_escape(displaypath, quote=False)

    r = []
    r.append('<!DOCTYPE html>\n<html>')
    r.append(f'<head>\n<meta charset="utf-8" />\n<title>{title}</title>\n</head>')
    r.append(f'<body>\n<h1>{title}</h1>')
    r.append('<hr>\n<ul>')
    for name in listing:
      fullname = path_join(path, name)
      displayname = linkname = name
      if is_dir(fullname, follow=True):
        displayname = name + '/'
        linkname = name + '/'
      link_href = url_quote(linkname, errors='replace')
      link_text = html_escape(displayname, quote=False)
      r.append(f'<li><a href="{link_href}">{link_text}</a></li>')
    r.append('</ul>\n<hr>\n</body>\n</html>\n')
    body = '\n'.join(r).encode(errors='replace')
    return HttpContent(body=body, content_type=html_content_type)


  def fake_favicon(self) -> None:
    'This was a hack to prevent favicon request errors from showing up in the logs.'
    if self.path == '/favicon.ico': # TODO: send actual favicon if it exists.
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
