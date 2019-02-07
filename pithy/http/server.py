# Derived from CPython 3.7 Lib/http/server.py.
# Changes dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from ..fs import is_dir, list_dir, norm_path, path_exists, path_join
from ..io import errL, errSL
from email.utils import formatdate as format_email_date
from html import escape as html_escape
from http import HTTPStatus
from http.client import HTTPException, HTTPMessage, LineTooLong, parse_headers # type: ignore
from io import BytesIO
from os import fstat as os_fstat
from posixpath import normpath, splitext
from shutil import copyfileobj
from socket import getfqdn as get_fully_qualified_domain_name, timeout as SocketTimeout
from socketserver import TCPServer, StreamRequestHandler
from sys import exc_info
from traceback import print_exception
from typing import Any, BinaryIO, List, Optional, Tuple, Type
from urllib.parse import unquote as url_unquote, urlsplit as url_split, urlunsplit as url_join
import mimetypes
import os
import sys
import time
import urllib.parse


__version__ = '0.1'

'''
- log requests even later (to capture byte count)
- log user-agent header and other interesting goodies
- send error log to separate file
'''

# Here's a quote from the NCSA httpd docs about log file format.
#
# The logfile format is as follows. Each line consists of:
#
# host rfc931 authuser [DD/Mon/YYYY:hh:mm:ss] "request" ddd bbbb
#
# host: Either the DNS name or the IP number of the remote client
# rfc931: Any information returned by identd for this person, - otherwise.
# authuser: If user sent a userid for authentication, the user name, - otherwise.
# DD: Day
# Mon: Month (calendar name)
# YYYY: Year
# hh: hour (24-hour format, the machine's timezone)
# mm: minutes
# ss: seconds
# request: The first line of the HTTP request as sent by the client.
# ddd: the status code returned by the server, - if not available.
# bbbb: the total number of bytes sent, *not including the HTTP/1.0 header*, - if not available.
# | You can determine the name of the file accessed through request.
#
# (Actually, the latter is only true if you know the server configuration
# at the time the request was made!)



__version__ = '1'

DEFAULT_ERROR_MESSAGE = '''\
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Error: {code}</title>
</head>
<body>
  <h1>Error: {code} - {label}</p>
  <p>{message}</p>
</body>
</html>
'''

DEFAULT_ERROR_CONTENT_TYPE = "text/html;charset=utf-8"


class HTTPServer(TCPServer):

  allow_reuse_address = True # Unclear what this implies.

  unrecoverable_exceptions: Tuple[Type, ...] = (
    AttributeError,
    ImportError,
    MemoryError,
    NameError,
    SyntaxError,
  )

  def server_bind(self):
    '''Override TCP.server_bind to store the server name.'''
    super().server_bind()
    host, port = self.server_address[:2]
    self.name = get_fully_qualified_domain_name(host)
    self.port = port

  def handle_error(self, request, client_address):
    '''
    Override BaseServer.handle_error to fail fast for unrecoverable errors.
    '''
    errL()
    errSL('Exception while processing request from client:', client_address)
    e_type, exc, traceback = info = exc_info()
    if isinstance(exc, self.unrecoverable_exceptions):
      raise Exception('unrecoverable error') from exc
    else:
      print_exception(e_type, exc, traceback)
      errL('-'*40)


class HTTPRequestHandler(StreamRequestHandler):

  sys_version = 'Python/{}.{}.{}'.format(*sys.version_info[:3])

  # The format is multiple whitespace-separated strings, where each string is of the form name[/version].
  server_version = f"pithy.http.Server/{__version__}"

  error_message_format = DEFAULT_ERROR_MESSAGE
  error_content_type = DEFAULT_ERROR_CONTENT_TYPE


  weekdayname = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

  monthname = [None, 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

  protocol_version = "HTTP/1.1"

  MessageClass = HTTPMessage

  # hack to maintain backwards compatibility
  responses = { v: (v.phrase, v.description) for v in HTTPStatus.__members__.values() }

  # The default request version.
  # This only affects responses up until the point where the request line is parsed,
  # so it mainly decides what the client gets back when sending a malformed request line.
  # Most web servers default to HTTP 0.9, i.e. don't send a status line.
  default_request_version = protocol_version


  if not mimetypes.inited: mimetypes.init()
  ext_mime_types = mimetypes.types_map.copy()
  ext_mime_types.update({
    '': 'text/plain', # Default.
  })


  def __init__(self, *args, directory:str=None, **kwargs) -> None:
    self.command:Optional[str] = None  # set in case of error on the first line.
    self.request_version = self.default_request_version
    self.close_connection = True
    self.requestline = ''
    self.directory = directory or os.getcwd()
    self.local_path: Optional[str] = None
    self.prevent_client_caching = True
    super().__init__(*args, **kwargs) # type: ignore # Calls handle.


  def handle(self):
    '''Handle multiple requests if necessary.'''
    self.close_connection = True

    self.handle_one_request()
    while not self.close_connection:
      self.handle_one_request()


  def handle_one_request(self):
    '''
    Handle a single HTTP request.
    '''
    try:
      self.raw_requestline = self.rfile.readline(65537)
      if len(self.raw_requestline) > 65536:
        self.requestline = ''
        self.request_version = ''
        self.command = ''
        self.send_error(HTTPStatus.REQUEST_URI_TOO_LONG)
        return
      if not self.raw_requestline:
        self.close_connection = True
        return
      if not self.parse_request():
        # An error code has been sent, just exit
        return
      mname = 'do_' + self.command
      if not hasattr(self, mname):
        self.send_error(
          HTTPStatus.NOT_IMPLEMENTED,
          "Unsupported method (%r)" % self.command)
        return
      method = getattr(self, mname)
      method()
      self.wfile.flush() #actually send the response if not already done.
    except SocketTimeout as e:
      #a read or a write timed out.  Discard this connection
      self.log_error("Request timed out: %r", e)
      self.close_connection = True
      return


  def parse_request(self):
    version = self.request_version
    self.requestline = requestline = str(self.raw_requestline, 'latin-1').rstrip('\r\n')
    words = requestline.split()
    if not words: return False
    if len(words) < 3:
      self.send_error(HTTPStatus.BAD_REQUEST, "Bad request syntax (%r)" % requestline)
      return False
    version = words[-1]
    try:
      if not version.startswith('HTTP/'): raise ValueError
      base_version_number = version.split('/', 1)[1]
      version_number = base_version_number.split(".")
      # RFC 2145 section 3.1 says:
      # * there can be only one ".";
      # * major and minor numbers MUST be treated as separate integers;
      # * HTTP/2.4 is a lower version than HTTP/2.13, which in turn is lower than HTTP/12.3;
      # * Leading zeros MUST be ignored by recipients.
      if len(version_number) != 2: raise ValueError
      version_number = int(version_number[0]), int(version_number[1])
    except (ValueError, IndexError):
      self.send_error(HTTPStatus.BAD_REQUEST, "Bad request version (%r)" % version)
      return False
    if version_number >= (1, 1) and self.protocol_version >= "HTTP/1.1": # TODO: the lexicographical comparison here is incorrect.
      self.close_connection = False
    if version_number >= (2, 0):
      self.send_error(HTTPStatus.HTTP_VERSION_NOT_SUPPORTED, "Invalid HTTP version (%s)" % base_version_number)
      return False
    self.request_version = version

    self.command, self.path = words[:2]

    # Examine the headers and look for a Connection directive.
    try:
      self.headers = parse_headers(self.rfile, _class=self.MessageClass)
    except LineTooLong as err:
      self.send_error(HTTPStatus.REQUEST_HEADER_FIELDS_TOO_LARGE, "Line too long", str(err))
      return False
    except HTTPException as err:
      self.send_error(HTTPStatus.REQUEST_HEADER_FIELDS_TOO_LARGE, "Too many headers", str(err))
      return False

    conntype = self.headers.get('Connection', "")
    if conntype.lower() == 'close':
      self.close_connection = True
    elif (conntype.lower() == 'keep-alive' and self.protocol_version >= "HTTP/1.1"): # TODO: lexicographical compare.
      self.close_connection = False

    expect = self.headers.get('Expect', "")
    if (expect.lower() == "100-continue" and self.protocol_version >= "HTTP/1.1" and self.request_version >= "HTTP/1.1"): # TODO: lexicographical compare.
      if not self.handle_expect_100(): return False

    # Compute local_path.
    p = self.path
    # abandon query and fragment parameters.
    p = p.partition('?')[0]
    p = p.partition('#')[0]
    has_trailing_slash = p.rstrip().endswith('/') # remember explicit trailing slash.
    p = url_unquote(p)
    p = norm_path(p)
    if '..' in p: return
    assert p.startswith('/')
    p = p[1:] # Remove leading slash. TODO: path_join should not use os.path.join, which behaves dangerously for absolute paths.
    p = norm_path(path_join(self.directory, p))
    if has_trailing_slash: p += '/'
    self.local_path = p
    return True


  def handle_expect_100(self):
    '''Decide what to do with an "Expect: 100-continue" header.

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


  def send_error(self, code:HTTPStatus, message:str=None, explain:str=None) -> None:
    '''Send and log an error reply.

    Arguments are
    * code:  an HTTP error code
           3 digits
    * message: a simple optional 1 line reason phrase.
           *( HTAB / SP / VCHAR / %x80-FF )
           defaults to short entry matching the response code
    * explain: a detailed message defaults to the long entry
           matching the response code.

    This sends an error response (so it must be called before any
    output has been generated), logs the error, and finally sends
    a piece of HTML explaining the error to the user.

    '''

    try:
      shortmsg, longmsg = self.responses[code]
    except KeyError:
      shortmsg, longmsg = '???', '???'
    if message is None:
      message = shortmsg
    if explain is None:
      explain = longmsg
    self.log_error("code %d, message %s", code, message)
    self.send_response(code, message)
    self.send_header('Connection', 'close')

    # Message body is omitted for cases described in:
    #  - RFC7230: 3.3. 1xx, 204(No Content), 304(Not Modified)
    #  - RFC7231: 6.3.6. 205(Reset Content)
    body = None
    if (code >= 200 and
      code not in (HTTPStatus.NO_CONTENT,
             HTTPStatus.RESET_CONTENT,
             HTTPStatus.NOT_MODIFIED)):
      # HTML encode to prevent Cross Site Scripting attacks
      # (see bug #1100201)
      content = (self.error_message_format % {
        'code': code,
        'message': html_escape(message, quote=False),
        'explain': html_escape(explain, quote=False)
      })
      body = content.encode('UTF-8', 'replace')
      self.send_header("Content-Type", self.error_content_type)
      self.send_header('Content-Length', int(len(body)))
    self.end_headers()

    if self.command != 'HEAD' and body:
      self.wfile.write(body)


  def send_response(self, code:HTTPStatus, message:str=None) -> None:
    '''
    Add the response header to the headers buffer and log the response code.

    Also send two standard headers with the server software
    version and the current date.

    '''
    self.log_request(code)
    self.send_response_only(code, message)
    self.send_header('Server', self.version_string())
    self.send_header('Date', self.format_header_date())
    if self.prevent_client_caching:
      self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
      self.send_header('Pragma', 'no-cache')
      self.send_header('Expires', '0')


  def send_response_only(self, code:HTTPStatus, message:str=None) -> None:
    '''Send the response header only.'''
    if self.request_version != 'HTTP/0.9':
      if message is None:
        if code in self.responses:
          message = self.responses[code][0]
        else:
          message = ''
      if not hasattr(self, '_headers_buffer'):
        self._headers_buffer:List[bytes] = []
      self._headers_buffer.append(("%s %d %s\r\n" % (self.protocol_version, code, message)).encode('latin-1', 'strict'))


  def send_header(self, keyword:str, value:Any) -> None:
    '''Send a MIME header to the headers buffer.'''
    if self.request_version != 'HTTP/0.9':
      if not hasattr(self, '_headers_buffer'):
        self._headers_buffer = []
      self._headers_buffer.append(("%s: %s\r\n" % (keyword, value)).encode('latin-1', 'strict'))

    if keyword.lower() == 'connection':
      if value.lower() == 'close':
        self.close_connection = True
      elif value.lower() == 'keep-alive':
        self.close_connection = False


  def end_headers(self) -> None:
    '''Send the blank line ending the MIME headers.'''
    if self.request_version != 'HTTP/0.9':
      self._headers_buffer.append(b"\r\n")
      self.flush_headers()


  def flush_headers(self) -> None:
    if hasattr(self, '_headers_buffer'):
      self.wfile.write(b"".join(self._headers_buffer))
      self._headers_buffer = []


  def log_error(self, format:str, *args:Any) -> None:
    '''
    Log an error.

    This is called when a request cannot be fulfilled. By default it passes the message on to log_message().
    Arguments are the same as for log_message().
    XXX This should go to the separate error log.
    '''
    self.log_message(format, *args)


  def version_string(self) -> str:
    '''Return the server software version string.'''
    return self.server_version + ' ' + self.sys_version


  def address_string(self) -> str:
    '''Return the client address.'''
    return self.client_address[0] # type: ignore


  def do_GET(self) -> None:
    '''Serve a GET request.'''
    f = self.send_head()
    if f:
      try: copyfileobj(f, self.wfile)
      finally: f.close()


  def do_HEAD(self) -> None:
    '''Serve a HEAD request.'''
    f = self.send_head()
    if f:
      f.close()


  def send_head(self) -> Optional[BinaryIO]:
    if self.path == '/favicon.ico': # TODO: send actual favicon if it exists.
      self.send_response(HTTPStatus.OK)
      self.send_header('Content-type', 'image/x-icon')
      self.send_header('Content-Length', 0)
      self.end_headers()
      return None

    if self.local_path is None:
      self.send_error(HTTPStatus.UNAUTHORIZED, "Path refers to parent directory")
      return None

    if is_dir(self.local_path):
      if not self.local_path.endswith('/'): # redirect browser to path with slash (what apache does).
        self.send_response(HTTPStatus.MOVED_PERMANENTLY)
        parts = list(url_split(self.path))
        parts[2] += '/'
        new_url = url_join(parts)
        self.send_header("Location", new_url)
        self.end_headers()
        return None
      for index in ("index.html", "index.htm"):
        index = path_join(self.local_path, index)
        if path_exists(index):
          self.local_path = index
          break
      else:
        return self.list_directory(self.local_path)

    ctype = self.guess_file_type(self.local_path)
    f: BinaryIO
    try:
      f = open(self.local_path, 'rb')
    except OSError:
      self.send_error(HTTPStatus.NOT_FOUND,
        message=f'File not found: {self.local_path}',
        explain=f'URI path: {self.path}')
      return None
    try:
      f_stat = os_fstat(f.fileno())
      self.send_response(HTTPStatus.OK)
      self.send_header("Content-type", ctype)
      self.send_header("Content-Length", f_stat.st_size)
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
      self.send_error(
        HTTPStatus.NOT_FOUND,
        "No permission to list directory")
      return None
    list.sort(key=lambda a: a.lower())
    r = []
    try:
      displaypath = urllib.parse.unquote(self.path,
                         errors='surrogatepass')
    except UnicodeDecodeError:
      displaypath = urllib.parse.unquote(path)
    displaypath = html_escape(displaypath, quote=False)
    enc = sys.getfilesystemencoding()
    title = 'Directory listing for %s' % displaypath
    r.append('<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">')
    r.append('<html>\n<head>')
    r.append('<meta http-equiv="Content-Type" content="text/html; charset=%s">' % enc)
    r.append('<title>%s</title>\n</head>' % title)
    r.append('<body>\n<h1>%s</h1>' % title)
    r.append('<hr>\n<ul>')
    for name in list:
      fullname = os.path.join(path, name)
      displayname = linkname = name
      # Append / for directories or @ for symbolic links
      if os.path.isdir(fullname):
        displayname = name + "/"
        linkname = name + "/"
      if os.path.islink(fullname):
        displayname = name + "@"
        # Note: a link to a directory displays with @ and links with /
      r.append('<li><a href="%s">%s</a></li>' % (urllib.parse.quote(linkname, errors='surrogatepass'), html_escape(displayname, quote=False)))
    r.append('</ul>\n<hr>\n</body>\n</html>\n')
    encoded = '\n'.join(r).encode(enc, 'surrogateescape')
    f = BytesIO()
    f.write(encoded)
    f.seek(0)
    self.send_response(HTTPStatus.OK)
    self.send_header("Content-type", "text/html; charset=%s" % enc)
    self.send_header("Content-Length", str(len(encoded)))
    self.end_headers()
    return f


  def guess_file_type(self, path:str) -> str:
    base, ext = splitext(path)
    ext = ext.lower()
    try: return self.ext_mime_types[ext]
    except KeyError: return self.ext_mime_types['']


  def log_message(self, format:str, *args:Any) -> None:
    'Base logging function called by all others. Overridden to alter formatting.'
    errL(f'{self.format_log_date()}: {self.address_string()} - {format%args}')


  def log_request(self, code='-', size='-') -> None:
    'Log an accepted request; called by send_response().'
    assert isinstance(code, HTTPStatus)
    self.log_message('%s %s "%s": %s', code.value, code.phrase, self.requestline, self.local_path)


  def format_log_date(self, timestamp:float=None) -> str:
    'Format the current time for logging.'
    if timestamp is None: timestamp = time.time()
    y, m, d, hh, mm, ss, wd, yd, is_dst = time.localtime(timestamp) # type: ignore
    return f'{y:04}-{m:02}-{d:02} {hh:02}:{mm:02}:{ss:02}.{timestamp%1:.03f}'


  def format_header_date(self, timestamp:float=None):
    'Format `timestamp` or now for an HTTP header value.'
    return format_email_date(time.time() if timestamp is None else timestamp, usegmt=True)
