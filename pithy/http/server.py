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
from http.client import HTTPException, HTTPMessage, LineTooLong, parse_headers
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

TODO: Update to threading / dual stack server as in stdlib http.server?
'''


__version__ = '1'

DEFAULT_ERROR_HTML = '''\
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Error: {code}</title>
</head>
<body>
  <h1>Error: {code} - {label}</h1>
  <p>{message}</p>
</body>
</html>
'''

DEFAULT_ERROR_CONTENT_TYPE = "text/html;charset=utf-8"


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

  sys_version = 'Python/{}.{}.{}'.format(*sys.version_info[:3])

  server_version = f"pithy.http.Server/{__version__}"
  #^ The format is multiple whitespace-separated strings, where each string is of the form name[/version].

  error_message_format = DEFAULT_ERROR_HTML
  error_content_type = DEFAULT_ERROR_CONTENT_TYPE

  protocol_version = "HTTP/1.1"

  MessageClass = HTTPMessage

  responses = { v: (v.phrase, v.description) for v in HTTPStatus.__members__.values() }

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


  def __init__(self, *args, **kwargs) -> None:
    self.request_line_bytes = b''
    self.request_line = ''
    self.command = ''
    self.close_connection = True
    self.prevent_client_caching = True
    self.headers: Optional[HTTPMessage] = None
    super().__init__(*args, **kwargs)


  def handle(self) -> None:
    '''
    Override point provided by BaseRequestHandler.
    Handle multiple requests if necessary.
    '''
    self.close_connection = True

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
        self.send_error(*error_args)
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


  def parse_request(self) -> Optional[tuple[HTTPStatus,str,str]]:
    self.request_line = request_line = str(self.request_line_bytes, 'latin-1').rstrip('\r\n')
    words = request_line.split(' ')
    if not words:
      return (HTTPStatus.BAD_REQUEST, 'Empty request line', '')
    if len(words) != 3:
      return (HTTPStatus.BAD_REQUEST, f'Bad request syntax: {request_line!r}', '')
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
      return (HTTPStatus.BAD_REQUEST, f'Bad request version: {version!r}', '')
    if version_number < (1, 1) or version_number >= (2, 0):
      return (HTTPStatus.HTTP_VERSION_NOT_SUPPORTED, f'Unsupported HTTP version: {version_number}', '')

    if command not in http_commands:
      return (HTTPStatus.BAD_REQUEST, f'Unrecognized HTTP command: {command!r}', '')

    self.command = command
    self.path = path

    # Examine the headers and look for a Connection directive.
    try:
      self.headers = parse_headers(self.rfile, _class=self.MessageClass) # type: ignore
    except LineTooLong as err:
      return (HTTPStatus.REQUEST_HEADER_FIELDS_TOO_LARGE, "Line too long", str(err))
    except HTTPException as err:
      return (HTTPStatus.REQUEST_HEADER_FIELDS_TOO_LARGE, "Too many headers", str(err))

    conn_type = self.headers.get('Connection', "").lower()
    if conn_type == 'close':
      self.close_connection = True
    elif conn_type == 'keep-alive':
      self.close_connection = False

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
    self.send_response_only(HTTPStatus.CONTINUE)
    self.end_headers()
    return True


  def send_error(self, code:HTTPStatus, label:str='', message:str='') -> None:
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

    try:
      dflt_label, dflt_message = self.responses[code]
    except KeyError:
      dflt_label, dflt_message = '???', '???'
    if not label:
      label = dflt_label
    if not message:
      message = dflt_message
    self.log_error(f'code: {code}; label: {label}')
    self.send_response(code, label)
    self.send_header('Connection', 'close')

    # Message body is omitted for cases described in:
    #  - RFC7230: 3.3. 1xx, 204 (No Content), 304 (Not Modified).
    #  - RFC7231: 6.3.6. 205 (Reset Content).
    body = None
    if (code >= 200 and code not in (HTTPStatus.NO_CONTENT, HTTPStatus.RESET_CONTENT, HTTPStatus.NOT_MODIFIED)):
      # HTML encode to prevent Cross Site Scripting attacks (see cpython bug #1100201).
      content = self.error_message_format.format(
        code=code, label=html_escape(label, quote=False), message=html_escape(message, quote=False))

      body = content.encode('UTF-8', 'replace')
      self.send_header("Content-Type", self.error_content_type)
      self.send_header('Content-Length', str(len(body)))
    self.end_headers()

    if self.command != 'HEAD' and body:
      self.wfile.write(body)


  def send_response(self, code:HTTPStatus, label:str=None) -> None:
    '''
    Add the response header to the headers buffer and log the response code.
    Also send two standard headers with the server software version and the current date.
    '''
    self.log_request(code)
    self.send_response_only(code, label)
    self.send_header('Server', f'{self.server_version} {self.sys_version}')
    self.send_header('Date', self.format_header_date())
    if self.prevent_client_caching:
      self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
      self.send_header('Pragma', 'no-cache')
      self.send_header('Expires', '0')


  def send_response_only(self, code:HTTPStatus, label:str=None) -> None:
    '''Send the response header only.'''
    if label is None:
      if code in self.responses:
        label = self.responses[code][0]
      else:
        label = ''
    if not hasattr(self, '_headers_buffer'):
      self._headers_buffer:List[bytes] = []
    self._headers_buffer.append(f'{self.protocol_version} {code} {label}\r\n'.encode('latin-1', 'strict'))


  def send_header(self, keyword:str, value:str) -> None:
    '''Send a MIME header to the headers buffer.'''

    if not hasattr(self, '_headers_buffer'):
      self._headers_buffer = []
    self._headers_buffer.append(f'{keyword}: {value}\r\n'.encode('latin-1', 'strict'))

    if keyword.lower() == 'connection':
      if value.lower() == 'close':
        self.close_connection = True
      elif value.lower() == 'keep-alive':
        self.close_connection = False


  def end_headers(self) -> None:
    '''Send the blank line ending the MIME headers.'''
    self._headers_buffer.append(b"\r\n")
    self.flush_headers()


  def flush_headers(self) -> None:
    if hasattr(self, '_headers_buffer'):
      self.wfile.write(b"".join(self._headers_buffer))
      self._headers_buffer = []


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
      self.send_response(HTTPStatus.OK)
      self.send_header('Content-type', 'image/x-icon')
      self.send_header('Content-Length', '0')
      self.end_headers()
      return None

    local_path = self.compute_local_path()
    if local_path is None:
      self.send_error(HTTPStatus.UNAUTHORIZED, "Path refers to parent directory")
      return None

    if is_dir(local_path, follow=True):
      if not local_path.endswith('/'): # redirect browser to path with slash (what apache does).
        self.send_response(HTTPStatus.MOVED_PERMANENTLY)
        parts = list(url_split(self.path))
        parts[2] += '/'
        new_url = url_join(parts)
        self.send_header("Location", new_url)
        self.end_headers()
        return None
      for index in ("index.html", "index.htm"):
        index = path_join(local_path, index)
        if path_exists(index, follow=False):
          local_path = index
          break
      else:
        return self.list_directory(local_path)

    if local_path.endswith('/'): # Actual file is not a directory. See CPython issue #17324.
      self.send_error(HTTPStatus.NOT_FOUND, "File not found")
      return None

    ctype = self.guess_file_type(local_path)
    f: BinaryIO
    try:
      f = open(local_path, 'rb')
    except OSError:
      self.send_error(HTTPStatus.NOT_FOUND, f'File not found: {local_path}', message=f'URI path: {self.path}')
      return None
    try:
      f_stat = os_fstat(f.fileno())
      self.send_response(HTTPStatus.OK)
      self.send_header("Content-type", ctype)
      self.send_header("Content-Length", str(f_stat.st_size))
      self.send_header("Last-Modified", self.format_header_date(f_stat.st_mtime))
      self.end_headers()
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
      list = os.listdir(path)
    except OSError:
      self.send_error(HTTPStatus.NOT_FOUND, "No permission to list directory")
      return None
    list.sort(key=lambda a: a.lower())
    r = []

    try:
      displaypath = urllib.parse.unquote(self.path, errors='replace')
    except UnicodeDecodeError:
      displaypath = urllib.parse.unquote(path)

    title = html_escape(displaypath, quote=False)

    r.append('<!DOCTYPE html>\n<html>')
    r.append(f'<head>\n<meta charset="utf-8" />\n<title>{title}</title>\n</head>')
    r.append(f'<body>\n<h1>{title}</h1>')
    r.append('<hr>\n<ul>')
    for name in list:
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
    self.send_response(HTTPStatus.OK)
    self.send_header("Content-type", "text/html; charset=utf-8")
    self.send_header("Content-Length", str(len(encoded)))
    self.end_headers()
    return f


  def guess_file_type(self, path:str) -> str:
    base, ext = splitext(path)
    ext = ext.lower()
    try: return self.ext_mime_types[ext]
    except KeyError: return self.ext_mime_types['']


  def log_message(self, msg:str) -> None:
    'Base logging function called by all others. Overridden to alter formatting.'
    errL(f'{self.format_log_date()}: {self.client_address_string()} - {msg}')


  def log_request(self, code='-', size='-') -> None:
    'Log an accepted request; called by send_response().'
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
