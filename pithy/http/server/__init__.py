# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from __future__ import annotations

import sys
from asyncio import (AbstractEventLoop, get_event_loop, IncompleteReadError, iscoroutine, run as aio_run, Server, start_server,
  StreamReader, StreamReaderProtocol, StreamWriter, wait_for)
from socket import AF_UNSPEC, AI_PASSIVE, socket as Socket
from ssl import SSLContext
from sys import stdout
from time import time as unix_time
from types import TracebackType
from typing import Any, Awaitable, Callable, Self, TextIO, TypeAlias

from ...io import errL, errLSSL, errSL
from ...logfmt import logfmt_items
from ...web import Request, Response, ResponseError
from ...web.app import WebApp
from .. import (BAD_REQUEST, CONTINUE, EXPECTATION_FAILED, http_method_bytes_to_enums, HttpException, may_send_body,
  METHOD_NOT_ALLOWED, NOT_IMPLEMENTED, OK, response_connection_close_line, response_header_date_line,
  response_status_line_for_exc)


__version__ = '0.1'
python_version = 'Python/{}.{}.{}'.format(*sys.version_info[:3])


DFLT_READ_LIMIT = 1<<16 # Same as asyncio.sterams._DEFAULT_LIMIT.

ClientConnectedCallback: TypeAlias = Callable[[StreamReader, StreamWriter], Awaitable[None] | None]


class HttpServer:

  server_version = f'pithy.http.server/{__version__} {python_version}'.encode('latin1')
  protocol_version = b'HTTP/1.1'

  server_response_header = b'Server: ' + server_version + b'\r\n'
  max_req_body_size = 1<<32 # 4 GiB.

  def __init__(self, *, app:WebApp, host:str='localhost', port:int=0, read_timeout:float=10.0, read_limit=DFLT_READ_LIMIT,
   reause_address:bool=False, reuse_port:bool=False, label:str='', out:TextIO=stdout, dbg:bool=False) -> None:

    self.host = host
    self.port = port
    self.read_timeout = read_timeout
    self.read_limit = read_limit
    self.reuse_address = reause_address
    self.reuse_port = reuse_port
    self.aio_server:Server|None = None
    self.label = label
    self.out = out
    self.dbg = dbg


  @property
  def url(self) -> str:
    if self.aio_server is None: raise RuntimeError('Server not started yet.')
    socket0 = self.aio_server.sockets[0]
    host, port = socket0.getsockname()
    return f'http://{host}:{port}/'


  async def __aenter__(self) -> Self:
    if self.aio_server is None:
      await self.create_aio_server(loop=get_event_loop())
    return self


  async def __aexit__(self, exc_type:type[BaseException]|None, exc:BaseException|None, tb:TracebackType|None) -> None:
    await self.close()
    if isinstance(exc, KeyboardInterrupt) and not self.dbg:
      exit('\nKeyboard interrupt.')


  async def create_aio_server(self, *, loop:AbstractEventLoop|None=None, family=AF_UNSPEC, flags=AI_PASSIVE,
   sock:Socket|None=None, backlog:int=100, ssl:SSLContext|None=None, reuse_address:bool=False, reuse_port:bool=False,
   ssl_handshake_timeout:float|None=None, ssl_shutdown_timeout:float|None=None, start_serving=True) -> Self:
    '''
    Start the server.
    Many of the options here are passed asyncio.BaseEventLoop.create_server().
    '''

    if self.aio_server is not None: raise RuntimeError('Server already started.')

    if loop is None: loop = get_event_loop()

    def protocol_factory():
      reader = StreamReader(limit=self.read_limit, loop=loop)
      return StreamReaderProtocol(reader, self.client_connected, loop=loop)

    common_args = dict(family=family, flags=flags, backlog=backlog, ssl=ssl, reuse_address=reuse_address, reuse_port=reuse_port,
      ssl_handshake_timeout=ssl_handshake_timeout, ssl_shutdown_timeout=ssl_shutdown_timeout, start_serving=start_serving)

    if sock:
      self.aio_server = await loop.create_server(protocol_factory=protocol_factory, sock=sock, **common_args)
    else:
      self.aio_server = await loop.create_server(protocol_factory=protocol_factory, host=self.host, port=self.port, **common_args)

    if start_serving: self.log(step='start', label=self.label, url=self.url)

    return self


  async def close(self) -> None:
    if aio_server := self.aio_server:
      self.aio_server = None
      aio_server.close()


  async def start_serving(self) -> None:
    if self.aio_server is None:
      raise RuntimeError('Server not started yet.')
    await self.aio_server.start_serving()


  async def serve_forever(self) -> None:
    if self.aio_server is None:
      raise RuntimeError('Server not started yet.')
    await self.aio_server.serve_forever()


  async def client_connected(self, reader:StreamReader, writer:StreamWriter) -> None:
    client_addr, client_port = writer.get_extra_info('peername')
    client = f'{client_addr}:{client_port}'
    self.log(c=client, step='connected')

    while True:
      try: head = await self.parse_http_head(reader, client)
      except Exception as e:
        # A parse error always closes the connection.
        # The client has either sent a syntactically invalid request or else is using an unsupported HTTP version.
        # Either way, they are unlikely to be able to recover, much less pipeline more requests.
        self.log(c=client, step='parse_head', exc=repr(e))
        writer.write(response_status_line_for_exc(e, self.dbg))
        writer.write(response_connection_close_line)
        await writer.drain()
        if self.dbg: raise
        break

      if not head: break # No request parsed. Do not respond and close the connection.

      try: await self.handle_request(head, reader, writer)
      except Exception as e:
        self.log(c=client, step='handle_request', exc=repr(e))
        writer.write(response_status_line_for_exc(e, self.dbg))
        await writer.drain()
        break

      await writer.drain() # Ensure data is sent.
      if head.connection_close: # TODO: break on shutdown flag?
        break
      else:
        continue

    writer.close()
    await writer.wait_closed()


  async def parse_http_head(self, reader:StreamReader, client:str) -> HttpRequestHead|None:
    timestamp = unix_time()
    timeout = self.read_timeout
    dbg = self.dbg

    # Read the request line; if we cannot then do not return a response.
    try: raw_req_line = await wait_for(reader.readuntil(b'\r\n'), timeout)
    except IncompleteReadError:
      return None
    except Exception as e:
      self.log(c=client, step='read_req_line', exc=repr(e))
      return None
    if not raw_req_line:
      self.log(c=client, step='check_req_line', err='empty')
      return None

    # Validate the request line.
    req_line = raw_req_line.rstrip(b'\r\n')
    self.log(c=client, req=req_line.decode('latin1'))
    req_words = req_line.split(b' ')
    if len(req_words) != 3:
      raise HttpException(BAD_REQUEST, f'Request line is not three words: {req_words!r}')

    # Request line: https://www.rfc-editor.org/rfc/rfc2616#section-5.1
    method, request_uri, http_version = req_words

    if not http_version.startswith(b'HTTP/'):
      raise HttpException(BAD_REQUEST, f'Request HTTP version prefix is not "HTTP/": {http_version!r}')
    version = http_version.removeprefix(b'HTTP/')
    if not version.startswith(b'1.'):
      raise ResponseError(BAD_REQUEST, f'Unsupported HTTP major version: {version!r}')
    v_minor_str = version.removeprefix(b'1.')
    if v_minor_str != b'1': raise ResponseError(BAD_REQUEST, f'Unsupported HTTP minor version: {version!r}')

    if method not in http_method_bytes_to_enums:
      raise HttpException(BAD_REQUEST, f'Unsupported HTTP method: {method!r}')

    match method:
      case b'CONNECT': raise HttpException(METHOD_NOT_ALLOWED, 'CONNECT method not supported.')
      case b'TRACE:': raise HttpException(METHOD_NOT_ALLOWED, 'TRACE method not supported.')

    head = HttpRequestHead(client=client, timestamp=timestamp, method=method, uri=request_uri)

    # Read the headers.
    has_host = False # Host header is required.

    while header_line := await wait_for(reader.readuntil(b'\r\n'), timeout):
      if header_line == b'\r\n': # End of headers.
        break
      key, colon, raw_val = header_line.partition(b':')
      if not colon: raise HttpException(BAD_REQUEST, f'No colon separator in header line: {header_line!r}')
      key = key.strip().title() # Convert to title case because headers are case-insensitive, and the canonical form is title case.
      val = raw_val.strip() # Do not lowercase the value for debug clarity.
      head.headers_list.append((key, val))
      match key:
        case b'Host': has_host = True
        case b'Connection':
          head.connection_close = (val == b'close')
          #^ Any other value indicates 'Keep-alive'.
          #^ See https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Connection#directives
        case b'Content-Length':
          try: content_length = int(val)
          except ValueError as e: raise HttpException(BAD_REQUEST, f'Invalid Content-Length header value: {val!r}')
          if content_length < 0:
            HttpException(BAD_REQUEST, 'Negative Content-Length header value.')
          if content_length > self.max_req_body_size:
            HttpException(BAD_REQUEST, 'Content-Length header value exceeds maximum allowed.')
          if head.content_length is not None and head.content_length != content_length:
            HttpException(BAD_REQUEST,
              'Multiple differing Content-Length headers: %d != %d' % (head.content_length, content_length))
          head.content_length = content_length
        case b'Expect':
          if val != b'100-continue':
            raise HttpException(EXPECTATION_FAILED, f'Unsupported Expect header value: {val!r}')
          raise HttpException(EXPECTATION_FAILED, '100-continue not supported.')
        case b'Transfer-Encoding':
          raise HttpException(NOT_IMPLEMENTED, 'Transfer-Encoding header not supported.')
        case b'Upgrade':
          raise HttpException(NOT_IMPLEMENTED, 'Upgrade header not supported.')

    else: # While loop exited with an empty line, implying a missing terminating CRLF line.
      raise HttpException(BAD_REQUEST, 'No terminating empty line for headers.')

    if not has_host: raise HttpException(BAD_REQUEST, 'No Host header.')

    return head


  async def handle_request(self, head:HttpRequestHead, reader:StreamReader, writer:StreamWriter) -> None:

    client = head.client

    if content_length := head.content_length:
      req_body = await wait_for(reader.readexactly(content_length), self.read_timeout)
    else:
      req_body = b''

    errSL('HANDLE', head.method, head.uri, req_body)
    errLSSL('headers:', *head.headers_list)

    writer.write(b'HTTP/1.1 200 OK\r\n')
    writer.write(self.server_response_header)
    writer.write(response_header_date_line())
    if head.connection_close: writer.write(response_connection_close_line)
    writer.write(b'Content-Type: text/plain\r\n')
    writer.write(b'Content-Length: %d\r\n' % (len(req_body),))
    writer.write(b'\r\n')
    writer.write(req_body)
    self.log(c=client, s='responded')


  def log(self, **items:Any) -> None:
    print(logfmt_items(items), file=self.out)


class HttpRequestHead:
  client:str
  timestamp:float
  method:bytes
  uri:bytes
  connection_close:bool
  content_length:int|None
  headers_list:list[tuple[bytes,bytes]]

  def __init__(self, client:str, timestamp:float, method:bytes, uri:bytes) -> None:
    self.client = client
    self.timestamp = timestamp
    self.method = method
    self.uri = uri
    self.connection_close = False
    self.content_length = None
    self.headers_list = []
