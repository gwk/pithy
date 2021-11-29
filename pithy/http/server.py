# Derived from cpython/Lib/http/server.py.
# Changes dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import mimetypes
import os
import sys
import time
import urllib.parse
from email.utils import formatdate as format_email_date
from html import escape as html_escape
from http import HTTPStatus
from http.client import HTTPException, HTTPMessage, parse_headers
from io import BytesIO
from os import fstat as os_fstat
from posixpath import splitext
from shutil import copyfileobj
from socket import getfqdn as get_fully_qualified_domain_name
from socketserver import StreamRequestHandler, TCPServer, ThreadingMixIn
from sys import exc_info
from traceback import print_exception
from typing import BinaryIO, List, Optional, Tuple, Type
from urllib.parse import unquote as url_unquote, urlsplit as url_split, urlunsplit as url_join

from ..fs import is_dir, norm_path, path_exists, path_join
from ..io import errL, errSL


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
  <h1>Error: {code} - {label}</h1>
</body>
</html>
'''

_default_error_content_type = "text/html;charset=utf-8"


class UnrecoverableServerError(Exception):
  'An error occurred for which the server cannot recover.'



class HTTPServer(TCPServer):

  allow_reuse_address = True # See cpython/Lib/socketserver.py.
  #^ Controls whether `self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)` is called.

  unrecoverable_exception_types: Tuple[Type, ...] = (
    AttributeError,
    ImportError,
    MemoryError,
    NameError,
    SyntaxError,
  )

  def __init__(self, server_address:Tuple[str,int], RequestHandlerClass:Type['HTTPRequestHandler'],
   bind_and_activate=True) -> None:

    super().__init__(server_address=server_address, RequestHandlerClass=RequestHandlerClass,
      bind_and_activate=bind_and_activate)


  def server_bind(self) -> None:
    '''Override TCP.server_bind to store the server name.'''
    super().server_bind()
    host, port = self.server_address[:2]
    self.server_name = get_fully_qualified_domain_name(host)
    self.server_port = port


  def handle_error(self, request, client_address) -> None:
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



class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class HTTPRequestHandler(StreamRequestHandler):

  server: HTTPServer # Covariant type override of BaseRequestHandler.

  python_version = 'Python/{}.{}.{}'.format(*sys.version_info[:3])

  server_version = f"pithy.http.server/{__version__} {python_version}"

  #^ The format is multiple whitespace-separated strings, where each string is of the form name[/version].

  error_html_format = _default_error_html_format
  error_content_type = _default_error_content_type

  protocol_version = "HTTP/1.1"

  MessageClass = HTTPMessage

  http_response_phrases = { v: v.phrase for v in HTTPStatus.__members__.values() }

  if not mimetypes.inited: mimetypes.init()
  ext_mime_types = mimetypes.types_map.copy()
  ext_mime_types.update({
    '': 'text/plain', # Default.
    '.bz2': 'application/x-bzip2',
    '.gz': 'application/gzip',
    '.sh': 'text/plain', # Show source instead of prompting download.
    '.xz': 'application/x-xz',
    '.z': 'application/octet-stream',
    })


  def __init__(self, request, client_address, server) -> None:
    self.request_line_bytes = b''
    self.request_line = ''
    self.command = ''
    self.close_connection = True
    self.prevent_client_caching = True # TODO: this should not be an instance variable.
    self.headers: Optional[HTTPMessage] = None
    self.response_buffer = bytearray() # Response line followed by header lines.
    super().__init__(request=request, client_address=client_address, server=server)


  def handle(self) -> None:
    '''
    Override point provided by BaseRequestHandler.
    Handle multiple requests if necessary.
    '''
    self.handle_one_request()
    while not self.close_connection:
      self.handle_one_request()


  def handle_one_request(self) -> None:
    '''
    Handle a single HTTP request.
    '''
    try:
      # Parse request.
      self.request_line_bytes = self.rfile.readline(65537)
      if len(self.request_line_bytes) > 65536:
        self.send_error(HTTPStatus.REQUEST_URI_TOO_LONG)
        return
      if not self.request_line_bytes:
        self.close_connection = True
        return
      if error_args := self.parse_request():
        code, label = error_args
        self.send_error(code=code, label=label)
        return
      # Handle 'Expect'.
      assert self.headers
      expect = self.headers.get('Expect', '').lower()
      if expect == '100-continue':
        if not self.handle_expect_100(): return
      # Determine method and dispatch.
      method_name = 'handle_http_' + self.command
      method = getattr(self, method_name, None)
      if not method:
        self.send_error(HTTPStatus.NOT_IMPLEMENTED, f'Unsupported method: {self.command!r}')
        return
      method()
      self.wfile.flush() # Send the response if not already done.
    except TimeoutError as e:
      # A read or a write timed out.  Discard this connection.
      self.log_error(f'Request timed out: {e}')
      self.close_connection = True
      return


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
      version_numbers = base_version_number.split(".")
      # RFC 2145 section 3.1 says:
      # * there can be only one ".";
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
      self.headers = parse_headers(self.rfile, _class=self.MessageClass) # type: ignore
    except HTTPException as exc:
      return (HTTPStatus.REQUEST_HEADER_FIELDS_TOO_LARGE, f'{type(exc)}: {exc}')

    # Respect connection directive.
    conn_type = self.headers.get('Connection', '').lower()
    if 'close' in conn_type:
      self.close_connection = True
    else:
      self.close_connection = False # Keep-alive is the default for HTTP/1.1.n
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
    p = p.lstrip('/') # Remove leading slash. TODO: path_join should not use os.path.join, which behaves dangerously for absolute paths.
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
    self.add_response_line(HTTPStatus.CONTINUE)
    self.end_headers_and_flush_response()
    return True


  def send_error(self, code:HTTPStatus, label:str='') -> None:
    '''
    Send and log an error reply.

    Arguments are:
    * code:  a 3 digit HTTP error code
    * label: a simple optional 1 line reason phrase.
      * ( HTAB / SP / VCHAR / %x80-FF ) (TODO: enforce these character requirements)
      * defaults to short entry matching the response code
    * message: a detailed message defaults to the long entry matching the response code.

    This sends an error response (so it must be called before any output has been generated),
    logs the error, and finally sends a piece of HTML explaining the error to the user.
    '''

    if not label:
      label = self.http_response_phrases.get(code, '???')
    self.log_error(f'code: {code}; label: {label}')
    self.add_response(code, label)
    self.close_connection = True

    # Message body is omitted for cases described in:
    #  - RFC7230: 3.3. 1xx, 204 (No Content), 304 (Not Modified).
    #  - RFC7231: 6.3.6. 205 (Reset Content).
    body = None
    if (code >= 200 and code not in (HTTPStatus.NO_CONTENT, HTTPStatus.RESET_CONTENT, HTTPStatus.NOT_MODIFIED)):
      content = self.error_html_format.format(code=code, label=html_escape(label, quote=False))
      #^ HTML-escape the label to prevent Cross Site Scripting attacks (see cpython bug #1100201).
      body = content.encode('UTF-8', 'replace')
      self.add_header("Content-Type", self.error_content_type)
      self.add_header('Content-Length', str(len(body)))

    self.end_headers_and_flush_response()
    if self.command != 'HEAD' and body:
      self.wfile.write(body)


  def add_response(self, code:HTTPStatus, label:str=None) -> None:
    '''
    Add the response header to the headers buffer and log the response code.
    Also send two standard headers with the server software version and the current date.
    '''
    self.log_request(code)
    self.add_response_line(code, label)
    self.add_header('Server', self.server_version)
    self.add_header('Date', self.format_header_date())
    if self.prevent_client_caching:
      self.add_header('Cache-Control', 'no-cache, no-store, must-revalidate')
      self.add_header('Pragma', 'no-cache')
      self.add_header('Expires', '0')


  def add_response_line(self, code:HTTPStatus, label:str=None) -> None:
    '''Add the response line only.'''
    if label is None:
      label = self.http_response_phrases.get(code, '')
    assert not self.response_buffer
    self.response_buffer.extend(f'{self.protocol_version} {code} {label}\r\n'.encode('latin1', 'strict'))


  def add_header(self, key:str, val:str) -> None:
    '''Add a MIME header to the headers buffer.'''
    self.response_buffer.extend(f'{key}: {val}\r\n'.encode('latin1', 'strict'))


  def end_headers_and_flush_response(self) -> None:
    '''
    Add a `Connection: close` header if appropriate, add the blank line ending the MIME headers, and flush the response.
    '''
    if self.close_connection:
      self.add_header('Connection', 'close')
    self.response_buffer.extend(b"\r\n")
    self.wfile.write(self.response_buffer)
    #print(self.response_buffer.decode('latin1'))
    self.response_buffer.clear()


  def handle_http_GET(self) -> None:
    '''Serve a GET request.'''
    f = self.send_head()
    if f:
      try: copyfileobj(f, self.wfile)
      finally: f.close()


  def handle_http_HEAD(self) -> None:
    '''Serve a HEAD request.'''
    f = self.send_head()
    if f:
      f.close()


  def send_head(self) -> Optional[BinaryIO]:
    if self.path == '/favicon.ico': # TODO: send actual favicon if it exists.
      self.add_response(HTTPStatus.OK)
      self.add_header('Content-type', 'image/x-icon')
      self.add_header('Content-Length', '0')
      self.end_headers_and_flush_response()
      return None

    local_path = self.compute_local_path()
    if local_path is None:
      self.send_error(HTTPStatus.UNAUTHORIZED, "Path refers to parent directory")
      return None

    if is_dir(local_path, follow=True):
      if not local_path.endswith('/'): # redirect browser to path with slash (what apache does).
        self.add_response(HTTPStatus.MOVED_PERMANENTLY)
        parts = list(url_split(self.path))
        parts[2] += '/'
        new_url = url_join(parts)
        self.add_header("Location", new_url)
        self.end_headers_and_flush_response()
        return None
      for index in ("index.html", "index.htm"):
        index = path_join(local_path, index)
        if path_exists(index, follow=False):
          local_path = index
          break
      else:
        return self.list_directory(local_path)

    if local_path.endswith('/'): # Actual file is not a directory. See CPython issue #17324.
      self.send_error(HTTPStatus.NOT_FOUND)
      return None

    ctype = self.guess_file_type(local_path)
    f: BinaryIO
    try:
      f = open(local_path, 'rb')
    except OSError:
      self.send_error(HTTPStatus.NOT_FOUND)
      return None
    try:
      f_stat = os_fstat(f.fileno())
      self.add_response(HTTPStatus.OK)
      self.add_header("Content-type", ctype)
      self.add_header("Content-Length", str(f_stat.st_size))
      self.add_header("Last-Modified", self.format_header_date(f_stat.st_mtime))
      self.end_headers_and_flush_response()
      return f
    except:
      f.close()
      raise


  def list_directory(self, path:str) -> Optional[BytesIO]:
    '''
    Helper to produce a directory listing (absent index.html).

    Return value is either a file object, or None (indicating an error).
    In either case, the headers are sent, making the interface the same as for send_head().
    '''
    try:
      listing = os.listdir(path)
    except OSError:
      self.send_error(HTTPStatus.NOT_FOUND)
      return None
    listing.sort(key=lambda a: a.lower())

    try:
      displaypath = urllib.parse.unquote(self.path, errors='replace')
    except UnicodeDecodeError:
      displaypath = urllib.parse.unquote(path)

    title = html_escape(displaypath, quote=False)

    r = []
    r.append('<!DOCTYPE html>\n<html>')
    r.append(f'<head>\n<meta charset="utf-8" />\n<title>{title}</title>\n</head>')
    r.append(f'<body>\n<h1>{title}</h1>')
    r.append('<hr>\n<ul>')
    for name in listing:
      fullname = path_join(path, name)
      displayname = linkname = name
      # Append / for directories or @ for symbolic links
      if os.path.isdir(fullname):
        displayname = name + "/"
        linkname = name + "/"
      if os.path.islink(fullname):
        displayname = name + "@"
      link_href = urllib.parse.quote(linkname, errors='replace')
      link_text = html_escape(displayname, quote=False)
      r.append(f'<li><a href="{link_href}">{link_text}</a></li>')
    r.append('</ul>\n<hr>\n</body>\n</html>\n')
    encoded = '\n'.join(r).encode(errors='replace')
    f = BytesIO()
    f.write(encoded)
    f.seek(0)
    self.add_response(HTTPStatus.OK)
    self.add_header("Content-type", "text/html; charset=utf-8")
    self.add_header("Content-Length", str(len(encoded)))
    self.end_headers_and_flush_response()
    return f


  def guess_file_type(self, path:str) -> str:
    base, ext = splitext(path)
    ext = ext.lower()
    try: return self.ext_mime_types[ext]
    except KeyError: return self.ext_mime_types['']


  def log_message(self, msg:str) -> None:
    'Base logging function called by all others.'
    errL(f'{self.format_log_date()}: {self.client_address_string()} - {msg}')


  def log_request(self, code:HTTPStatus) -> None:
    'Log an accepted request; called by add_response().'
    assert isinstance(code, HTTPStatus)
    self.log_message(f'{code.value} {code.phrase} {self.request_line!r}')


  def log_error(self, msg:str) -> None:
    '''Log an error. Called when a request cannot be fulfilled. By default it passes the message on to log_message().'''
    self.log_message(msg)


  def format_log_date(self, timestamp:float=None) -> str:
    'Format the current time for logging.'
    if timestamp is None: timestamp = time.time()
    ts = time.localtime(timestamp)
    y, m, d, hh, mm, ss, wd, yd = ts[:8]
    return f'{y:04}-{m:02}-{d:02} {hh:02}:{mm:02}:{ss:02}.{timestamp:.03f}'


  def format_header_date(self, timestamp:float=None):
    'Format `timestamp` or now for an HTTP header value.'
    return format_email_date(time.time() if timestamp is None else timestamp, usegmt=True)

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
