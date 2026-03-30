# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Sequence
from dataclasses import dataclass
from http import HTTPStatus
from io import BufferedReader
from queue import Full as QueueFull, LifoQueue
from socket import AF_INET, SO_REUSEADDR, SOCK_STREAM, socket as Socket, SOL_SOCKET
from threading import Event, Thread
from typing import cast, Literal
from urllib.parse import urlsplit as url_split

from h11 import (Connection as h11_Connection, ConnectionClosed as h11_ConnectionClosed, Data as h11_Data, DONE as h11_DONE,
  EndOfMessage as h11_EndOfMessage, IDLE as h11_IDLE, InformationalResponse as h11_InformationalResponse,
  NEED_DATA as h11_NEED_DATA, ProtocolError as h11_ProtocolError, RemoteProtocolError as h11_RemoteProtocolError,
  Request as h11_Request, Response as h11_Response, SEND_BODY as h11_SEND_BODY, SEND_RESPONSE as h11_SEND_RESPONSE,
  SERVER as h11_SERVER)
from pithy.logging import logE, logI

from ..http import http_method_bytes_to_strs, may_send_body
from .app import WebApp
from .request import AddrPair, Request, RequestConn
from .response import Response, ResponseError


BAD_REQUEST = HTTPStatus.BAD_REQUEST


class HttpStateError(Exception):
  'Raised when H11 is in an unexpected state.'


class BodyAlreadyReadError(Exception):
  'Raised when the request body has already been read.'


class BodyTooLargeError(Exception):
  'Raised when the request body is larger than the maximum allowed size.'

  def __init__(self, *, length:int, max_bytes:int) -> None:
    super().__init__(f'{length=}; {max_bytes=}.')
    self.length = length
    self.max_bytes = max_bytes


@dataclass(slots=True)
class _Conn():
  client_addr:AddrPair
  socket:Socket
  h11_conn:h11_Connection
  recv_size:int
  error:h11_ProtocolError|TimeoutError|None = None # Set when an error occurs.


  def handle_need_data(self) -> bool:
    '''
    Handle a h11_NEED_DATA event by receiving data from the socket and feeding it to h11.
    Returns True on success.
    If an error occurs, `self.error` is set and False is returned.
    '''
    try:
      data = self.socket.recv(self.recv_size)
      self.h11_conn.receive_data(data)
      return True
    except (TimeoutError, h11_RemoteProtocolError) as e:
      self.error = e
      return False


  def next_request(self) -> h11_Request|None:
    '''
    Returns the next Request.
    If an error occurs, `self.error` is set and None is returned.
    '''
    assert self.h11_conn.our_state is h11_IDLE
    while True:
      event = self.h11_conn.next_event()
      if event is h11_NEED_DATA:
        if self.handle_need_data(): continue
        return None # Error set.
      if isinstance(event, h11_ConnectionClosed): return None # No error set.
      if isinstance(event, h11_Request): return event
      else: raise HttpStateError(f'next_request expected Request event; received: {event!r}.')


  def next_data(self) -> h11_Data|None:
    '''
    Returns the next Data event, or None if the end of the body is reached.
    If an error occurs, `self.error` is set and None is returned.
    '''
    assert self.h11_conn.their_state is h11_SEND_BODY
    while True:
      event = self.h11_conn.next_event()
      if event is h11_NEED_DATA:
        if self.handle_need_data(): continue
        return None # Error set.
      if isinstance(event, h11_Data):
        assert event.data
        return event
      if isinstance(event, h11_EndOfMessage): return None # End of body reached; no error set.
      else: raise HttpStateError(f'next_data expected Data event; received: {event!r}.')


  def next_completion(self) -> h11_EndOfMessage|None:
    '''
    Returns the EndOfMessage event indicating the end of the request/response cycle.
    If an error occurs, `self.error` is set and None is returned.
    '''
    assert self.h11_conn.our_state in (h11_SEND_RESPONSE, h11_SEND_BODY)
    while True:
      event = self.h11_conn.next_event()
      if event is h11_NEED_DATA:
        if self.handle_need_data(): continue
        return None # Error set.
      if isinstance(event, h11_EndOfMessage): return event
      else: raise HttpStateError(f'next_completion expected EndOfMessage event; received: {event!r}.')


  def recycle(self) -> bool:
    '''
    Recycle the connection for the next request/response cycle if possible.
    If True is returned, then the connection is ready for the next request/response cycle.
    If False is returned, then the connection must be closed.
    If an error occurred, logs the error, clear it, and return False.
    '''
    if self.error:
      logE('Connection error.', error=self.error, client_addr=self.client_addr)
      self.error = None
      return False
    if self.h11_conn.our_state is h11_DONE and self.h11_conn.their_state is h11_DONE:
      self.h11_conn.start_next_cycle()
      return True
    return False


class WebServerRequestConn(RequestConn):

  def __init__(self, content_length:int|None, _conn:_Conn) -> None:
    self.content_length = content_length
    self._conn = _conn
    self._bytes_read = 0
    self._was_body_read = False


  def read_some(self, max_bytes:int) -> bytes:

    if self._was_body_read: raise BodyAlreadyReadError('Request body has already been read.')

    if self.content_length is not None and self.content_length > max_bytes:
      raise BodyTooLargeError(length=self.content_length, max_bytes=max_bytes)

    event = self._conn.next_data()
    if isinstance(event, h11_Data):
      self._bytes_read += len(event.data)
      if self._bytes_read > max_bytes:
        raise BodyTooLargeError(length=self._bytes_read, max_bytes=max_bytes)
      return event.data
    return b''


  def read_body(self, max_bytes:int) -> bytes:
    chunks = []
    while True:
      chunk = self.read_some(max_bytes)
      if not chunk: break
      chunks.append(chunk)
    return b''.join(chunks)




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
          logI('Queue full; dropping connection.', client_addr=client_addr)
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
    socket.settimeout(self.config.conn_timeout)
    h11_conn = h11_Connection(h11_SERVER)
    conn = _Conn(client_addr=client_addr, socket=socket, h11_conn=h11_conn, recv_size=self.config.recv_size)

    try:
      while event := conn.next_request():
        method = http_method_bytes_to_strs.get(event.method, '')
        response = self._handle_connection_cycle(conn, event, method)
        self._send_response(conn, response=response, method=method)
        if not conn.recycle(): break
    finally:
      try: socket.close()
      except OSError: pass


  def _handle_connection_cycle(self, conn:_Conn, event:h11_Request, method:str) -> Response:
    '''
    Handles a single request/response cycle on the connection.
    Returns a Response object.
    '''

    if event.http_version != b'1.1':
      http_version_str = event.http_version.decode('ascii', errors='replace')
      return Response(HTTPStatus.HTTP_VERSION_NOT_SUPPORTED,
        body=f'Only HTTP 1.1 is supported; received {http_version_str!r}.').set_connection_close()

    if not method:
      return Response(HTTPStatus.NOT_IMPLEMENTED,
        body=f'Non-standard method: {event.method.decode("ascii", errors="replace")!r}.').set_connection_close()

    try:
      target = event.target.decode('ascii') # A UnicodeDecodeError here is unexpected since h11 should have validated it.
      url = url_split(target) # A ValueError here is unlikely given that h11 has already validated, and urlsplit is permissive.
    except (UnicodeDecodeError, ValueError):
      return Response(BAD_REQUEST, body=f'Bad target/path: {event.target.decode("ascii", errors="replace")!r}.'
        ).set_connection_close()

    headers = self._headers_dict(event.headers)

    content_length:int|None = None
    if cl_str := headers.get('content-length'):
      content_length = int(cl_str) # Assume that h11 has already validated the content-length value.

    request = Request(
      client_addr=conn.client_addr,
      method=method,
      scheme='http',
      host=self.config.host,
      port=self.config.port,
      path=url.path or '/',
      query=url.query,
      headers=headers,
      content_length=content_length,
      conn=WebServerRequestConn(content_length=content_length, _conn=conn))

    if conn.h11_conn.client_is_waiting_for_100_continue:
      expect_response = self.app.handle_expect_100_continue(request)
      if expect_response.status == HTTPStatus.CONTINUE:
        self._send_informational_response(conn.h11_conn, conn.socket, expect_response)
      else:
        return expect_response.set_connection_close() # The body was not read, so the connection cannot be reused.

    try:
      response = self.app.handle_request(request)
      # The app may or may not read the body.
      if conn.h11_conn.their_state is h11_SEND_BODY: # The app did not read the body.
        response.set_connection_close() # The connection cannot be reused since the body was not read.

    except ResponseError as exc:
      response = Response.from_error(exc, method=method)

    return response


  def _send_error(self, conn:_Conn, status:HTTPStatus, reason:str) -> Literal[False]:
    response = Response(status=status, body=reason, media_type='text/plain')
    response.set_connection_close()
    self._send_response(conn, response=response, method='GET')
    return False


  def _send_bad_req(self, conn:_Conn, reason:str) -> Literal[False]:
    return self._send_error(conn, HTTPStatus.BAD_REQUEST, reason)


  def _request_wants_connection_close(self, headers:dict[str,str]) -> bool:
    'Return True if the connection should be closed after the current response.'
    return 'close' in {t.strip() for t in headers.get('connection', '').lower().split(',')}


  def _headers_dict(self, headers:Sequence[tuple[bytes,bytes]]) -> dict[str,str]:
    '''
    Converts the sequence of bytes pairs from h11 into a dict of strings with keys lowercased.
    If there are multiple headers with the same name, their values are combined into a single comma-separated string.
    '''
    result:dict[str,str] = {}
    for key_b, val_b in headers:
      key = key_b.decode('ascii').lower() # Ascii key has already been validated by h11_
      val = val_b.decode('latin1') # Decode cannot fail.
      try: result[key] = f'{result[key]}, {val}'
      except KeyError: result[key] = val
    return result


  def _send_informational_response(self, h11_conn:h11_Connection, socket:Socket, response:Response) -> None:
    event = h11_InformationalResponse(status_code=response.status.value, headers=response.headers_bytes_list())
    socket.sendall(h11_conn.send(event))


  def _send_response(self, conn:_Conn, *, response:Response, method:str) -> None:
    event = h11_Response(status_code=response.status.value, headers=response.headers_bytes_list(), reason=response.reason)
    h11_conn = conn.h11_conn
    socket = conn.socket

    socket.sendall(h11_conn.send(event))

    if may_send_body(method, response.status):
      body = response.body
      if isinstance(body, BufferedReader):
        self._send_body_file(h11_conn, socket, body)
        body.close()
      elif body:
        socket.sendall(h11_conn.send(h11_Data(data=cast(bytes, body))))
        #^ bytearray is bytes-like; h11.Data is documented to accept any bytes-like object despite the type being `bytes`.

    socket.sendall(h11_conn.send(h11_EndOfMessage()))


  def _send_body_file(self, h11_conn:h11_Connection, socket:Socket, file:BufferedReader) -> None:
    while True:
      chunk = file.read(self.config.recv_size)
      if not chunk: break
      socket.sendall(h11_conn.send(h11_Data(data=chunk)))
      if not chunk: break
      socket.sendall(h11_conn.send(h11_Data(data=chunk)))
