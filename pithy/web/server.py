# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Sequence
from dataclasses import dataclass
from http import HTTPStatus
from io import BufferedReader, BytesIO
from queue import Full as QueueFull, LifoQueue
from socket import AF_INET, SO_REUSEADDR, SOCK_STREAM, socket as Socket, SOL_SOCKET
from threading import Event, Thread
from typing import cast
from urllib.parse import SplitResult as Url, urlsplit as url_split

import h11
from pithy.logging import logI

from ..http import http_method_bytes_to_strs, may_send_body
from .app import WebApp
from .request import AddrPair, Request
from .response import Response, ResponseError


@dataclass(slots=True, frozen=True)
class ServerConfig:
  '''
  host: the hostname or IP address to bind to; defaults to 'localhost'.
  port: the port number to bind to; defaults to 0, which means the OS will choose a free port.
  backlog: the number of unaccepted connections that the system will allow before refusing new connections.
  conn_timeout: the timeout in seconds for blocking operations on client connections.
  max_queued: the maximum number of connections waiting in the queue; excess connections are dropped immediately.
  num_threads: the number of worker threads in the thread pool.
  recv_size: the maximum number of bytes to receive at once from client connections.
  log_access: whether to log each request after it is handled.
  thread_name_prefix: the prefix for thread names of worker threads.

  Note: to read the actual port, use WebServer.port after initializing the server, since it may be dynamically assigned.
  '''
  host:str = 'localhost'
  port:int = 0
  backlog:int = 128
  recv_size:int = 64 * 1024
  conn_timeout:float = 10.0
  num_threads:int = 4
  max_queued:int = 64
  thread_name_prefix:str = 'WebServer'
  log_access:bool = True


type ConnQueueItem = tuple[Socket,AddrPair]


class WebServer:
  '''
  WebServer is a multithreaded HTTP 1.1 server.
  It uses a LIFO queue for incoming connections, on the assumption that under load it is better to serve some requests quickly
  and let others time out, rather than have all requests delayed or time out.
  '''

  def __init__(self, *, app:WebApp, config:ServerConfig=ServerConfig()) -> None:
    '''
    Initialize the web server.
    The server will bind to the host and port specified in the config.
    If port 0 was specified then the dynamically assigned port is saved in `self.port`.
    '''

    self.app = app
    self.config = config
    self._stop = Event()
    self._conn_queue: LifoQueue[ConnQueueItem|None] = LifoQueue(maxsize=config.max_queued)
    self._workers: list[Thread] = []

    socket = Socket(AF_INET, SOCK_STREAM)
    self._socket = socket
    socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    socket.bind((config.host, config.port))
    socket.listen(config.backlog)
    socket.settimeout(1.0) # This is the timeout for accepting new connections, not for client connections.

    self.scheme = 'http'
    self.host = config.host
    self.port = (config.port or socket.getsockname()[1])


  @property
  def url(self) -> str:
    return f'{self.scheme}://{self.host}:{self.port}'


  def serve_forever(self) -> None:
    'Starts the server loop; call shutdown() from another thread to stop the server and then this method will return.'
    cfg = self.config
    logI('Serving.', url=self.url)

    for i in range(cfg.num_threads):
      thread = Thread(target=self._worker, daemon=False, name=f'{cfg.thread_name_prefix}-worker-{i}')
      thread.start()
      self._workers.append(thread)

    try:
      while not self._stop.is_set():
        try:
          conn_sock, client_addr = self._socket.accept()
        except TimeoutError:
          continue
        except OSError:
          if self._stop.is_set(): break  # shutdown() closes the socket to unblock accept(); the resulting OSError is expected.
          raise
        try:
          self._conn_queue.put_nowait((conn_sock, client_addr))
        except QueueFull:
          logI('Connection queue full; dropping connection.', client_addr=client_addr)
          conn_sock.close()
    except KeyboardInterrupt:
      logI('Interrupted.')
    finally:
      try: self._socket.close()
      except OSError: pass
      for _ in self._workers: self._conn_queue.put(None)  # Signal each worker to exit.
      for thread in self._workers: thread.join()


  def shutdown(self) -> None:
    self._stop.set()
    try: self._socket.close()
    except OSError: pass  # The socket may already be closed (e.g. if finally block in serve_forever() ran first).


  def _worker(self) -> None:
    'Worker thread entry point.'
    while True:
      item = self._conn_queue.get()
      if item is None: break
      socket, client_addr = item
      self._handle_connection(socket, client_addr)


  def _handle_connection(self, socket:Socket, client_addr:AddrPair) -> None:
    'Handle a single client connection in a worker thread.'
    h11_conn = h11.Connection(h11.SERVER)
    socket.settimeout(self.config.conn_timeout)

    try:
      while event := self._next_event(h11_conn, socket, client_addr):
        if isinstance(event, h11.ConnectionClosed): break

        assert isinstance(event, h11.Request), \
          f'Unexpected event in connection loop (Data/EndOfMessage should be consumed by _read_body): {event!r}'

        if event.http_version != b'1.1':
          http_version_str = event.http_version.decode('ascii', errors='replace')
          self._send_error(h11_conn, socket, client_addr, HTTPStatus.HTTP_VERSION_NOT_SUPPORTED,
            f'Only HTTP 1.1 is supported; received {http_version_str!r}.')
          break

        method = http_method_bytes_to_strs.get(event.method)
        if method is None:
          self._send_error(h11_conn, socket, client_addr, HTTPStatus.NOT_IMPLEMENTED,
            f'Method not implemented: {event.method.decode("ascii", errors="replace")!r}.')
          break

        close_connection = True

        try: request_path = url_split(event.target.decode('ascii', errors='replace')).path
        except UnicodeDecodeError, ValueError: request_path = '?'

        try:
          request = self._build_request(event, method, h11_conn, socket, client_addr)
          response = self.app.handle_request(request)
          close_connection = self._should_close(request.headers)
        except EarlyResponse as exc:
          response = exc.response
          request = exc.request
          # Body was not read, so the connection cannot be reused.
        except ResponseError as exc:
          response = Response.from_error(exc, method=method)

        if close_connection:
          response.set_connection_close_header()

        self._send_response(h11_conn, socket, response, method)
        if self.config.log_access:
          logI('Request.', client=client_addr[0], method=method, path=request_path, status=response.status.value)
        if close_connection: break
        h11_conn.start_next_cycle()

    finally:
      try: socket.close()
      except OSError: pass


  def _build_request(self, event:h11.Request, method:str, h11_conn:h11.Connection, socket:Socket, client_addr:AddrPair) -> Request:
    headers = self._headers_dict(event.headers)

    target = event.target.decode('ascii', errors='replace')
    url = url_split(target)

    if self._expects_body(headers):
      expect = headers.get('expect', '').lower()
      if expect == '100-continue':
        preview = self._preview_request(method, url, headers, client_addr)
        expect_response = self.app.handle_expect_100_continue(preview)
        if expect_response.status == HTTPStatus.CONTINUE:
          self._send_informational(h11_conn, socket, expect_response)
        else:
          raise EarlyResponse(preview, expect_response)
    # Always consume through EndOfMessage so h11 reaches DONE on both sides,
    # which is required for start_next_cycle() to work on keep-alive connections.
    # For no-body requests h11 returns EndOfMessage immediately with empty data.
    body = self._read_body(h11_conn, socket, client_addr)

    content_length = len(body)
    body_file = BytesIO(body)

    return Request(
      method=method,
      scheme='http',
      host=self.config.host,
      port=self.config.port,
      path=url.path or '/',
      query=url.query,
      body_file=body_file,
      headers=headers,
      client_addr=client_addr,
      content_length=content_length)


  def _preview_request(self, method:str, url:Url, headers:dict[str,str], client_addr:AddrPair) -> Request:
    return Request(
      method=method,
      scheme='http',
      host=self.config.host,
      port=self.config.port,
      path=url.path or '/',
      query=url.query,
      body_file=BytesIO(b''),
      headers=headers,
      client_addr=client_addr,
      content_length=0)


  def _read_body(self, h11_conn:h11.Connection, socket:Socket, client_addr:AddrPair) -> bytes:
    parts:list[bytes] = []
    while True:
      event = self._next_event(h11_conn, socket, client_addr)
      if event is None: break
      if isinstance(event, h11.Data):
        parts.append(event.data)
      elif isinstance(event, h11.EndOfMessage):
        break
      elif isinstance(event, h11.ConnectionClosed):
        break
    return b''.join(parts)


  def _next_event(self, h11_conn:h11.Connection, socket:Socket, client_addr:AddrPair) \
   -> h11.Request|h11.Data|h11.EndOfMessage|h11.ConnectionClosed|None:
    while True:
      try:
        event = h11_conn.next_event()
      except h11.RemoteProtocolError:
        self._send_error(h11_conn, socket, client_addr, HTTPStatus.BAD_REQUEST, 'Bad request')
        return None
      if event is h11.NEED_DATA:
        try: data = socket.recv(self.config.recv_size)
        except TimeoutError:
          return None
        if not data:
          return None
        try: h11_conn.receive_data(data)
        except h11.RemoteProtocolError:
          self._send_error(h11_conn, socket, client_addr, HTTPStatus.BAD_REQUEST, 'Bad request')
          return None
        continue
      if event is h11.PAUSED:
        return None
      return cast(h11.Request|h11.Data|h11.EndOfMessage|h11.ConnectionClosed, event)


  def _send_error(self, h11_conn:h11.Connection, socket:Socket, client_addr:AddrPair, status:HTTPStatus, reason:str) -> None:
    response = Response(status=status, body=reason, media_type='text/plain')
    response.set_connection_close_header()
    self._send_response(h11_conn, socket, response, 'GET')


  def _should_close(self, headers:dict[str,str]) -> bool:
    'Return True if the connection should be closed after the current response.'
    return 'close' in {t.strip() for t in headers.get('connection', '').lower().split(',')}


  def _headers_dict(self, headers:Sequence[tuple[bytes,bytes]]) -> dict[str,str]:
    result:dict[str,str] = {}
    for key_b, val_b in headers:
      key = key_b.decode('ascii', errors='replace').lower()
      val = val_b.decode('latin1', errors='replace')
      try: result[key] = f'{result[key]}, {val}'
      except KeyError: result[key] = val
    return result


  def _expects_body(self, headers:dict[str,str]) -> bool:
    if 'content-length' in headers:
      try: return int(headers['content-length']) > 0
      except ValueError: return True
    return headers.get('transfer-encoding', '').lower() == 'chunked'



  def _send_informational(self, h11_conn:h11.Connection, socket:Socket, response:Response) -> None:
    event = h11.InformationalResponse(status_code=response.status.value, headers=response.headers_bytes_list())
    socket.sendall(h11_conn.send(event))


  def _send_response(self, h11_conn:h11.Connection, socket:Socket, response:Response, method:str) -> None:
    event = h11.Response(status_code=response.status.value, headers=response.headers_bytes_list())

    socket.sendall(h11_conn.send(event))

    if may_send_body(method, response.status):
      body = response.body
      if isinstance(body, BufferedReader):
        self._send_body_file(h11_conn, socket, body)
        body.close()
      elif body:
        socket.sendall(h11_conn.send(h11.Data(data=cast(bytes, body))))
        # bytearray is bytes-like, so passing it as bytes is safe; the cast avoids a spurious type error.

    socket.sendall(h11_conn.send(h11.EndOfMessage()))


  def _send_body_file(self, h11_conn:h11.Connection, socket:Socket, file:BufferedReader) -> None:
    while True:
      chunk = file.read(self.config.recv_size)
      if not chunk: break
      socket.sendall(h11_conn.send(h11.Data(data=chunk)))


class EarlyResponse(Exception):
  'Accept 100-continue handling.'
  def __init__(self, request:Request, response:Response) -> None:
    self.request = request
    self.response = response
    super().__init__(f'Early response: {response.status}')
