# Derived from cpython/Lib/http/server.py.
# Changes dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
This server implementation was originally derived from the stdlib http.server.
It was originally derived from CPython 3.7, then updated with changes from 3.10.0.
The last reviewed CPython commit was 058f9b27d3; not all changes were ported.
Since then it has been completely rewritten.

`Expect: 100-continue` handling was minimally tested using curl:
curl -X POST -H 'Expect: 100-continue' -d "user=name&pass=12345" http://localhost:8080
'''

import sys
import time
from datetime import datetime as DateTime
from http import HTTPStatus
from http.client import HTTPException, HTTPMessage, parse_headers
from io import BufferedIOBase, BufferedReader
from os import close, environ
from shutil import copyfileobj
from socket import socket as Socket
from socketserver import StreamRequestHandler, ThreadingTCPServer
from sys import exc_info, stderr
from traceback import print_exception
from typing import cast, IO, TextIO
from urllib.parse import SplitResult as Url, urlsplit as url_split

from ..web import Request, Response, ResponseError
from ..web.app import WebApp
from . import http_methods


__version__ = '0'


class UnrecoverableServerError(Exception):
  'An error occurred for which the server cannot recover.'


class HttpServer(ThreadingTCPServer):
  '''
  HttpServer is an HTTP/1.1 server.
  In order to serve HTTP 1.1 with keep-alive, the class needs multithreading.
  This is poorly explained in the stdlib http.server implementation.
  ThreadingTCPServer inherits from ThreadingMixIn and TCPServer.
  '''

  daemon_threads = True # Same as http.server.ThreadingHTTPServer.

  allow_reuse_address = True # See cpython/Lib/socketserver.py.
  #^ Controls whether `self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)` is called.

  unrecoverable_exception_types:tuple[type,...] = (
    AttributeError,
    ImportError,
    MemoryError,
    NameError,
    SyntaxError,
  )

  python_version = 'Python/{}.{}.{}'.format(*sys.version_info[:3])

  server_version = f'pithy.http.server/{__version__} {python_version}'
  #^ The format is multiple whitespace-separated strings, where each string is of the form name[/version].

  protocol_version = 'HTTP/1.1'

  # Instance properties.
  app:WebApp
  dbg:bool
  host:str
  port:int
  bound_host:str
  err:TextIO


  def __init__(self, *, host:str, port:int, app:WebApp, err=stderr, bind_and_activate=True):

    self.host = host
    self.port = port
    self.app = app
    self.err = err

    self.dbg = environ.get('DEBUG') is not None
    self.server_name = ''

    super().__init__(server_address=(host, port), RequestHandlerClass=HttpRequestHandler,
      bind_and_activate=bind_and_activate)


  def server_bind(self) -> None:
    '''Override TCP.server_bind to store the server name.'''
    super().server_bind()
    print(f'Serving {self.host}:{self.port}…')



  def handle_error(self, request:Socket|tuple[bytes,Socket], client_address:str|tuple[str,int]) -> None:
    '''
    This method overrides BaseServer.handle_error to fail fast for unrecoverable errors.
    '''
    print('Exception while handling request from client:', client_address, file=self.err)
    e_type, exc, traceback = exc_info()
    if isinstance(exc, self.unrecoverable_exception_types):
      raise UnrecoverableServerError from exc
    else:
      print_exception(e_type, exc, traceback)
      print('-'*40, file=self.err)


class HttpRequestHandler(StreamRequestHandler):

  server: HttpServer

  request_line_bytes: bytes
  request_line: str
  method: str
  target: str
  url: Url
  headers: dict[str,str]
  close_connection: bool


  def __init__(self, request:Socket|tuple[bytes,Socket], client_address:tuple[str,int], server:HttpServer):
    self.reset()
    self.reuse_count = 0
    super().__init__(request=request, client_address=client_address, server=server)


  def reset(self) -> None:
    self.request_line_bytes = b''
    self.request_line = ''
    self.method = ''
    self.target = ''
    self.url = url_split('')
    self.headers = {} # The request headers.
    self.close_connection = True


  def handle(self) -> None:
    '''
    Override point provided by BaseRequestHandler.
    Handle multiple requests if necessary.
    '''
    self.handle_one_request()
    while not self.close_connection:
      self.reset()
      self.reuse_count += 1
      try: self.handle_one_request()
      except ConnectionResetError as e:
        self.log_message(f'Connection reset by peer after {self.reuse_count} requests.', file=self.server.err)
        self.close_connection = True
      except TimeoutError as e:
        # Either a read or a write timed out. Discard this connection.
        self.log_message(f'Request timed out: {e}', file=self.server.err)
        self.close_connection = True


  def handle_one_request(self) -> None:
    '''
    Handle a single HTTP request.
    '''
    try:
      self.request_line_bytes = self.rfile.readline(65537)
      # If no data is received, do not send a response; just close the connection.
      if not self.request_line_bytes: return

      self.parse_request()

      request = Request(
        method=self.method,
        scheme='http', # TODO: this is not accurate.
        host=self.server.host,
        port=self.server.port,
        path=self.url.path,
        query=self.url.query,
        body_file=self.rfile,
        err=self.server.err,
        is_multiprocess=False,
        is_multithread=True,
        headers=self.headers)

      app = self.server.app

      # Handle 'Expect' header.
      expect = self.headers.get('Expect', '').lower()
      if expect == '100-continue':
        expect_response = app.handle_expect_100_continue(request)
        self.send_response(expect_response)
        if expect_response.status != HTTPStatus.CONTINUE:
          #^ According to this curl mailing list thread https://curl.se/mail/lib-2004-08/0002.html,
          # we must either close the connection or read the request body and discard it.
          # Alternatively, we could choose some length threshold below which we would read and discard the body.
          assert self.close_connection
          return

      # Handle request.
      response = app.handle_request(request)
      reason = ''

    except ResponseError as e:
      self.close_connection = True
      response = e.response(self.method)
      reason = e.reason

    app.fill_response_headers(request, response, close_connection=self.close_connection)
    self.send_response(response, reason=reason)


  def parse_request(self) -> None:
    if len(self.request_line_bytes) > 65536:
      raise ResponseError(HTTPStatus.REQUEST_URI_TOO_LONG, reason='Request-URI Too Long')
    self.request_line = request_line = str(self.request_line_bytes, 'latin1').rstrip('\r\n')
    words = request_line.split(' ')
    if not words:
      raise ResponseError(HTTPStatus.BAD_REQUEST, 'Empty request line')
    if len(words) != 3:
      raise ResponseError(HTTPStatus.BAD_REQUEST, f'Bad request syntax: {request_line!r}')
    method, target, version = words
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
      raise ResponseError(HTTPStatus.BAD_REQUEST, f'Bad request version: {version!r}')
    if version_number < (1, 1) or version_number >= (2, 0):
      raise ResponseError(HTTPStatus.HTTP_VERSION_NOT_SUPPORTED, f'Unsupported HTTP version: {version_number}')

    if method not in http_methods:
      raise ResponseError(HTTPStatus.BAD_REQUEST, f'Unrecognized HTTP method: {method!r}')

    self.method = method
    self.target = target
    try: self.url = url_split(target)
    except ValueError: pass

    # Parse headers.
    try: raw_headers = parse_headers(cast(BufferedIOBase, self.rfile), _class=HTTPMessage)
    except HTTPException as exc:
      raise ResponseError(HTTPStatus.REQUEST_HEADER_FIELDS_TOO_LARGE, f'{type(exc)}: {exc}')
    for key, val in raw_headers.items():
      # Conversion to dict must take into account possible reapeated headers, which by the spec should be joined into a single comma-separated value.
      try: self.headers[key] = f'{self.headers[key]}, {val}'
      except KeyError: self.headers[key] = val

    # Respect connection directive.
    conn_type = self.headers.get('Connection', '').lower()
    if 'close' in conn_type:
      assert self.close_connection # This was set to True in self.reset().
    else:
      self.close_connection = False # Keep-alive is the default for HTTP/1.1.


  def send_response(self, response:Response, reason:str='') -> None:
    '''
    Send the response line and headers to the client.
    Adds a `Connection: close` header if `close_connection` is set.
    '''

    status = response.status
    headers = response.headers

    self.log_message(f'{status.value} {reason} {self.request_line!r}', file=self.server.err)

    if self.close_connection:
      headers['Connection'] = 'close'

    buffer = bytearray(f'{self.server.protocol_version} {status.value} {reason}\r\n'.encode('latin1'))
    for k, v in headers.items():
      buffer.extend(k.encode('latin1'))
      buffer.extend(b': ')
      assert isinstance(v, (float, int, str))
      buffer.extend(str(v).encode('latin1'))
      buffer.extend(b'\r\n')
    buffer.extend(b'\r\n')

    if self.server.dbg:
      resp_str = buffer.decode('latin1', errors='replace')
      for line in resp_str.splitlines(keepends=True):
        print(f'  DBG: {line!r}', file=self.server.err)
      print(file=self.server.err)

    self.wfile.write(buffer)

    body = response.body
    if self.method != 'HEAD' and body:
      if isinstance(body, BufferedReader):
        try: copyfileobj(cast(IO, body), self.wfile)
        except OSError as e:
          # No way to report the error to the client at this point.
          print(f'Error while writing response body file: {e}', file=self.server.err)
      elif body:
        self.wfile.write(body)

    if isinstance(body, BufferedReader):
      body.close()


  def log_message(self, msg:str, *, file:TextIO) -> None:
    'Base logging function called by all others.'
    print(f'{DateTime.now()}  {self.client_address_ip()}: {msg}', file=file)


  def client_address_ip(self) -> str:
    '''Return the client address, omitting the port.'''
    return cast(str, self.client_address[0])
