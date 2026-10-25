# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Sequence
from dataclasses import dataclass, field
from errno import ENOTCONN
from http import HTTPStatus
from io import BufferedReader
from os import _exit as os_exit
from queue import Full as QueueFull, LifoQueue
from selectors import DefaultSelector, EVENT_READ
from socket import AF_INET, SHUT_WR, SO_REUSEADDR, SOCK_STREAM, socket as Socket, socketpair, SOL_SOCKET
from threading import Event, Lock, Thread
from time import monotonic
from traceback import clear_frames
from typing import cast, Literal
from urllib.parse import urlsplit as url_split

from h11 import (Connection as h11_Connection, ConnectionClosed as h11_ConnectionClosed, Data as h11_Data, DONE as h11_DONE,
  EndOfMessage as h11_EndOfMessage, Event as h11_Event, IDLE as h11_IDLE, InformationalResponse as h11_InformationalResponse,
  NEED_DATA as h11_NEED_DATA, PAUSED as h11_PAUSED, RemoteProtocolError as h11_RemoteProtocolError, Request as h11_Request,
  Response as h11_Response, SEND_BODY as h11_SEND_BODY, SERVER as h11_SERVER)
from pithy.logs import log, logE, logI, LogLevel

from ..http import http_method_bytes_to_strs, may_send_body
from .app import WebApp
from .auth import check_access, validate_privileges
from .env import web_host, web_port
from .errorrender import render_error_text
from .errors import ResponseError
from .request import AddrPair, Request, RequestConn
from .requestconn import BodyAlreadyReadError, BodyTooLargeError, ClientProtocolError
from .response import close_response_body, Response


_context_keywords_ = ['access logging', 'connection draining', 'h11', 'http 1.1', 'http.server', 'keep alive', 'multithreading',
  'request dispatch', 'socket', 'thread pool']


BAD_REQUEST = HTTPStatus.BAD_REQUEST


type _ConnStage = Literal['request_headers', 'request_body', 'request_completion', 'drain_body']
'The most recent read stage of a connection, recorded in protocol failure logs.'


class HttpStateError(Exception):
  'Raised when H11 is in an unexpected state.'


@dataclass(slots=True)
class _Conn():
  '''
  _Conn represents the internal state of a client connection through one or more connection keep-alive cycles.
  It exists to encapsulate the underlying H11 calls by narrowing the return type from next_event() for each stage,
  and to provide a handle through which the WebServerRequestConn can read the request body.
  Requests refer to this connection; it must not retain requests, which would create an ownership cycle.
  '''
  client_addr:AddrPair
  socket:Socket
  h11_conn:h11_Connection
  recv_size:int
  started:float = field(default_factory=monotonic)
  received_bytes:int = 0
  'Connection-wide bytes received from the socket, including pipelined requests.'
  pending_request:bool = False
  stage:_ConnStage = 'request_headers'
  response_sent:bool = False
  method:str = ''
  http_version:str = ''
  error:ClientProtocolError|None = None
  '''
  The first receive failure of the connection, set and logged when a read times out or h11 rejects received data.
  Once set, the connection is closed after the current cycle. An idle keep-alive timeout is not a failure.
  h11 exceptions are replaced because their messages embed received bytes; the replacement is constructed outside of
  the handling block so that it carries no reference to the original.
  Body and completion reads raise it, so its traceback can refer to the frames that hold the request;
  the traceback is cleared at the end of each cycle.
  '''
  response_status:int|None = None # Set once final response headers have been sent.


  def handle_need_data(self) -> bool:
    '''
    Handle a h11_NEED_DATA event by receiving data from the socket and feeding it to h11.
    Returns True on success, and False on an idle timeout or a failure; a failure also sets and logs `self.error`.
    '''
    try:
      data = self.socket.recv(self.recv_size)
      self.received_bytes += len(data)
      self.pending_request |= bool(data)
      self.h11_conn.receive_data(data)
      return True
    except TimeoutError:
      if not self.pending_request: return False # Ordinary idle connection.
      status = HTTPStatus.REQUEST_TIMEOUT
    except h11_RemoteProtocolError as exc:
      status = _status_for_h11_error(exc)
    self.fail(ClientProtocolError(status))
    return False


  def next_event(self) -> h11_Event|type[h11_NEED_DATA]|type[h11_PAUSED]:
    '''
    Returns the next h11 event. A protocol error is replaced by a logged ClientProtocolError.

    h11 converts a parsing error to RemoteProtocolError by re-raising it from a frame that refers to the exception.
    That reference cycle keeps every frame of the eventual traceback alive until garbage collection,
    including the application and connection cycle frames that hold the request.
    '''
    try: return self.h11_conn.next_event()
    except h11_RemoteProtocolError as exc:
      clear_frames(exc.__traceback__) # Clear frames to break the cycle; the executing frame is skipped and line info remains.
      status = _status_for_h11_error(exc)
    raise self.fail(ClientProtocolError(status))


  def next_request(self) -> h11_Request|None:
    '''
    Returns the next Request, or None when the client closed the connection or an idle keep-alive timeout elapsed.
    A read failure also returns None and sets `self.error`; malformed request headers raise ClientProtocolError.
    '''
    self.stage = 'request_headers'
    assert self.h11_conn.our_state is h11_IDLE
    while True:
      event = self.next_event()
      if event is h11_NEED_DATA:
        if self.handle_need_data(): continue
        return None # Idle timeout or failure.
      if isinstance(event, h11_ConnectionClosed): return None
      if isinstance(event, h11_Request): return event
      else: raise HttpStateError(f'next_request expected Request event; received: {type(event).__name__}.')


  def next_data(self) -> h11_Data|None:
    '''
    Returns the next Data event, or None if the end of the body is reached.
    Raises ClientProtocolError for a read failure; partial bodies must not be treated as complete.
    '''
    if self.stage != 'drain_body': self.stage = 'request_body'
    assert self.h11_conn.their_state is h11_SEND_BODY
    while True:
      event = self.next_event()
      if event is h11_NEED_DATA:
        if self.handle_need_data(): continue
        assert self.error is not None
        raise self.error
      if isinstance(event, h11_Data):
        assert event.data
        return event
      if isinstance(event, h11_EndOfMessage): return None # End of body reached; no error set.
      else: raise HttpStateError(f'next_data expected Data event; received: {type(event).__name__}.')


  def drain_unread_body(self, max_bytes:int) -> bool:
    '''
    Read and discard the unread remainder of the request body, up to `max_bytes`.
    Returns True if the body was fully consumed, False if the limit was reached. Raises ClientProtocolError for a read failure.
    See WebServer._close_connection for why this is necessary.
    '''
    assert self.h11_conn.their_state is h11_SEND_BODY
    self.stage = 'drain_body'
    count = 0
    while count <= max_bytes:
      event = self.next_data()
      if event is None: return True
      count += len(event.data)
    return False # The client is sending more than we are willing to read.


  def recycle(self) -> bool:
    '''
    Recycle the connection for the next request/response cycle if possible.
    If True is returned, then the connection is ready for the next request/response cycle.
    If False is returned, then the connection must be closed.
    If a failure occurred, then False is returned.
    '''
    if self.error is not None: return False
    if self.h11_conn.our_state is h11_DONE and self.h11_conn.their_state is h11_DONE:
      self.h11_conn.start_next_cycle()
      self.response_status = None
      self.response_sent = False
      self.method = self.http_version = ''
      self.pending_request = bool(self.h11_conn.trailing_data[0])
      return True
    return False


  def fail(self, error:ClientProtocolError) -> ClientProtocolError:
    '''
    Record the first failure of the connection as `self.error` and log it; later failures are not logged again.
    Returns `error` for the caller to raise.

    Failures are logged where they are detected, so the record stays accurate even if the application swallows the error.
    The record holds protocol facts only, never request bytes. Duration and received bytes cover the entire connection.
    Stage, response facts and sanitized request fields describe the current keep-alive cycle. Response sent means at least
    one complete header block was sent, including informational responses; response_status is null until final response
    headers are sent. Targets and headers are deliberately omitted. Only recognized methods and HTTP versions are included.

    A drain failure after the final response is logged at info level. Clients commonly stop uploading after an early
    rejection such as a 413, and the failure then only affects connection teardown.
    '''
    if self.error is not None: return error
    self.error = error
    level:LogLevel = 'info' if self.stage == 'drain_body' and self.response_status is not None else 'error'
    log(level, 'protocol_failure', status=error.status.value, stage=self.stage, client_addr=self.client_addr,
      elapsed=round(monotonic() - self.started, 3), received_bytes=self.received_bytes, response_sent=self.response_sent,
      response_status=self.response_status, method=self.method, http_version=self.http_version)
    return error


def _status_for_h11_error(exc:h11_RemoteProtocolError) -> HTTPStatus:
  'The response status that h11 suggests for a rejected request, defaulting to 400 for codes that HTTPStatus lacks.'
  try: return HTTPStatus(exc.error_status_hint)
  except ValueError: return HTTPStatus.BAD_REQUEST


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
    self._was_body_read = True
    return b''


  def read_body(self, max_bytes:int) -> bytes:
    chunks = []
    while True:
      chunk = self.read_some(max_bytes)
      if not chunk: break
      chunks.append(chunk)
    return b''.join(chunks)



def _split_target(target:bytes) -> tuple[str,str]:
  '''
  Split a raw request target into (path, query).
  Raises ValueError for targets that urlsplit rejects, which is unlikely since urlsplit is permissive.
  h11 restricts the target to printable ASCII, so UnicodeDecodeError is not expected.
  '''
  url = url_split(target.decode('ascii'))
  return url.path or '/', url.query


@dataclass(frozen=True)
class ServerConfig:
  '''
  host: the hostname or IP address to bind to; defaults to 'localhost'.
  port: the port number to bind to; defaults to 0, which means the OS will choose a free port.
  backlog: the number of unaccepted connections that the system will allow before refusing new connections.
  conn_timeout: the timeout in seconds for blocking operations on client connections.
  drain_timeout: the timeout in seconds for blocking reads while draining an unread request body before closing a connection.
  drain_max_bytes: the maximum number of unread request body bytes to drain before closing a connection.
  max_queued: the maximum number of connections waiting in the queue; excess connections are dropped immediately.
  num_threads: the number of worker threads in the thread pool.
  recv_size: the maximum number of bytes to receive at once from client connections.
  log_access: whether to log each parsed HTTP request after response sending completes or fails.
    Access fields are c (client), u (uid from request.ctx, default 0), m (method), p (path), q (raw query), s (status), and d (duration).
    Duration is in seconds, from receipt of request headers through response sending, excluding connection cleanup.
    Status is the sent response status; it does not guarantee body delivery.
    It is 0 if no response headers were sent, whether because the client left or because a server error aborted the cycle,
    so that client disconnects do not count as 5xx responses; the cause is in the adjacent protocol_failure or error record.
    Client protocol failures and incomplete-request timeouts produce separate protocol_failure records, even when disabled.
  startup_message: an optional info message logged immediately after the serving URL.
  prevent_client_caching: whether to prevent clients from caching responses.
  thread_name_prefix: the prefix for thread names of worker threads.

  Note: to read the actual port, use WebServer.port after initializing the server, since it may be dynamically assigned.
  '''
  host:str = field(default_factory=web_host)
  port:int = field(default_factory=web_port)
  backlog:int = 128
  recv_size:int = 64 * 1024
  conn_timeout:float = 10.0
  drain_timeout:float = 1.0
  drain_max_bytes:int = 1 << 20
  num_threads:int = 4
  max_queued:int = 64
  thread_name_prefix:str = 'WebServer'
  log_access:bool = True
  startup_message:str = ''
  prevent_client_caching:bool = False


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
    self._lock = Lock()  # Guards _serving, which decides whether shutdown() or serve_forever() closes the sockets.
    self._serving = False
    self._wakeup_reader, self._wakeup_writer = socketpair()
    self._wakeup_writer.setblocking(False)
    self._conn_queue: LifoQueue[ConnQueueItem|None] = LifoQueue(maxsize=config.max_queued)
    self._workers: list[Thread] = []

    socket = Socket(AF_INET, SOCK_STREAM)
    self._socket = socket
    socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    socket.bind((config.host, config.port))
    socket.listen(config.backlog)
    socket.setblocking(False)
    #^ On macOS accepted sockets inherit the non-blocking flag; _handle_connection resets it with settimeout.

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
    if cfg.startup_message: logI(cfg.startup_message)

    for i in range(cfg.num_threads):
      thread = Thread(target=self._worker, daemon=False, name=f'{cfg.thread_name_prefix}-worker-{i}')
      thread.start()
      self._workers.append(thread)

    try:
      with self._lock:
        if self._stop.is_set(): return  # shutdown() was called first and has already closed the sockets.
        self._serving = True
      with DefaultSelector() as selector:
        selector.register(self._wakeup_reader, EVENT_READ)
        selector.register(self._socket, EVENT_READ)
        while not self._stop.is_set():
          selector.select()
          #^ The wakeup reader is never drained; it only becomes readable once _stop is set, so the loop exits.
          if self._stop.is_set(): break
          try: conn_sock, client_addr = self._socket.accept()
          except BlockingIOError: continue  # The pending connection was reset before it could be accepted.
          try:
            self._conn_queue.put_nowait((conn_sock, client_addr))
          except QueueFull:
            logI('Queue full; dropping connection.', client_addr=client_addr)
            conn_sock.close()
    except KeyboardInterrupt:
      logI('Interrupted.')
    finally:
      with self._lock:
        self._serving = False
        self._close_sockets()
      for _ in self._workers: self._conn_queue.put(None)  # Signal each worker to exit.
      for thread in self._workers: thread.join()


  def shutdown(self) -> None:
    '''
    Request shutdown, waking the accept loop immediately. Active requests finish before serve_forever returns.

    Closing a listening socket from another thread does not reliably wake accept on Unix, so a socket pair is used instead.
    If serve_forever is not running then the sockets are closed here, so that a server that never served does not leak them.
    '''
    with self._lock:
      if self._stop.is_set(): return
      self._stop.set()
      if self._serving: self._wakeup_writer.send(b'\0')
      else: self._close_sockets()


  def _close_sockets(self) -> None:
    'Close the listener and the wakeup pair; safe to call repeatedly.'
    self._socket.close()
    self._wakeup_reader.close()
    self._wakeup_writer.close()


  def _worker(self) -> None:
    'Worker thread entry point.'
    while True:
      item = self._conn_queue.get()
      if item is None: break
      socket, client_addr = item
      try:
        self._handle_connection(socket, client_addr)
      except BaseException as exc:
        logE('Uncaught worker exception; exiting process.', exc=exc, client_addr=client_addr)
        os_exit(1)


  def _handle_connection(self, socket:Socket, client_addr:AddrPair) -> None:
    'Handle a single client connection in a worker thread.'
    socket.settimeout(self.config.conn_timeout)
    h11_conn = h11_Connection(h11_SERVER)
    conn = _Conn(client_addr=client_addr, socket=socket, h11_conn=h11_conn, recv_size=self.config.recv_size)

    try:
      try:
        while event := conn.next_request():
          method = conn.method = http_method_bytes_to_strs.get(event.method, '')
          conn.http_version = event.http_version.decode('ascii') if event.http_version in (b'1.0', b'1.1') else ''
          self._handle_connection_cycle(conn, event, method)
          if not conn.recycle(): break
      except ClientProtocolError: pass # Logged when detected.
      if conn.error is not None and conn.h11_conn.our_state is h11_IDLE and not conn.h11_conn.trailing_data[1]:
        # Malformed or incomplete request headers from a client that is still connected: answer with a bare response.
        # h11 permits a response before any request. Later failures were answered during the cycle, or the client has closed.
        response = self._bare_response(conn.error.status, method='').set_connection_close()
        try: self._send_response(conn, response=response, method='')
        except OSError: pass # The client has gone.
    except Exception as exc:
      logE('Connection handling error.', exc=exc, client_addr=client_addr)
    finally:
      self._close_connection(conn)


  def _handle_connection_cycle(self, conn:_Conn, event:h11_Request, method:str) -> None:
    'Own the request through dispatch, response sending and access logging, releasing it before waiting for another request.'
    start_time = monotonic()
    request:Request|None = None
    try:
      result = self._make_request(conn, event, method)
      if isinstance(result, Request):
        request = result
        response = self._handle_request(conn, request)
      else:
        response = result
      body = response.body
      try:
        if self.config.prevent_client_caching: response.set_no_cache_headers()
        self._send_response(conn, response=response, method=method)
      finally:
        close_response_body(body)
    finally:
      try:
        if self.config.log_access: self._log_access(conn, event, start_time, request)
      finally:
        if conn.error is not None: conn.error.__traceback__ = None
        #^ Release the frames of this cycle, including those of the original socket read, which refer to the request.


  def _log_access(self, conn:_Conn, event:h11_Request, start_time:float, request:Request|None) -> None:
    'Log at the server boundary so that application dispatch and early rejections are always covered.'
    dur = round(monotonic() - start_time, 3)
    if request is None:
      try: path, query = _split_target(event.target)
      except (UnicodeDecodeError, ValueError): # Log the rejected target faithfully; backslashreplace emits only ASCII.
        path, query = event.target.decode('ascii', errors='backslashreplace'), ''
      client_addr = conn.client_addr
      uid = 0
    else:
      path, query = request.raw_path, request.query_str
      client_addr = request.client_addr
      uid = request.ctx.get('uid', 0)
    logI('access', c=client_addr[0] if client_addr else '-', u=uid,
      m=event.method.decode('ascii', errors='replace'), p=path, q=query,
      s=conn.response_status if conn.response_status is not None else 0, d=dur)


  def _close_connection(self, conn:_Conn) -> None:
    '''
    Close a client connection, first draining any unread request body.

    Closing a socket whose kernel receive buffer still holds unread data causes the kernel to send an RST instead of a FIN.
    The RST aborts the connection at the client, which fails its remaining sends and can discard response bytes
    that it has not yet read. This turns a well-formed error response (e.g. the 413 that we send when a body exceeds
    the handler limit) into a connection reset error on the client, nondeterministically depending on timing.

    To avoid this we half-close the socket, which tells the client that no more response data is coming
    while still allowing it to finish uploading, and then read the rest of the body before closing.
    The drain is bounded by `drain_max_bytes` and by `drain_timeout` per read,
    so that a client which keeps uploading cannot occupy the worker thread indefinitely.
    '''
    socket = conn.socket
    try:
      # An incompletely read body may leave unread data buffered. Only attempt draining if no failure has been recorded.
      if conn.error is None and conn.h11_conn.their_state is h11_SEND_BODY:
        try: socket.shutdown(SHUT_WR)
        except OSError as exc:
          if exc.errno == ENOTCONN: return # The client disconnected; there is nothing left to drain.
          raise
        socket.settimeout(self.config.drain_timeout)
        if not conn.drain_unread_body(max_bytes=self.config.drain_max_bytes):
          logI('Unread request body was not drained; closing connection abruptly.', client_addr=conn.client_addr)
    except ClientProtocolError: pass # Logged when detected.
    except Exception as exc:
      # Cleanup is best effort: request processing has ended, and a socket error here means the client left early.
      logI('Connection close error.', exc=exc, client_addr=conn.client_addr)
    finally:
      try: socket.close()
      except OSError: pass


  def _make_request(self, conn:_Conn, event:h11_Request, method:str) -> Request|Response:
    'Construct a request, or return a protocol rejection response before application dispatch.'

    if event.http_version != b'1.1':
      http_version_str = event.http_version.decode('ascii', errors='replace')
      return Response(HTTPStatus.HTTP_VERSION_NOT_SUPPORTED,
        body=f'Only HTTP 1.1 is supported; received {http_version_str!r}.').set_connection_close()

    if not method:
      return Response(HTTPStatus.NOT_IMPLEMENTED,
        body=f'Non-standard method: {event.method.decode("ascii", errors="replace")!r}.').set_connection_close()

    try: path, query = _split_target(event.target)
    except (UnicodeDecodeError, ValueError):
      return Response(BAD_REQUEST, body='Invalid request target.').set_connection_close()

    headers = self._headers_dict(event.headers)

    content_length:int|None = None
    if cl_str := headers.get('content-length'):
      content_length = int(cl_str) # Assume that h11 has already validated the content-length value.

    return Request(
      client_addr=conn.client_addr,
      method=method,
      scheme='http',
      host=self.config.host,
      port=self.config.port,
      raw_path=path,
      query_str=query,
      headers=headers,
      content_length=content_length,
      prevent_client_caching=self.config.prevent_client_caching,
      conn=WebServerRequestConn(content_length=content_length, _conn=conn))


  def _handle_request(self, conn:_Conn, request:Request) -> Response:
    'Dispatch a constructed request through application hooks and complete its framing.'
    method = request.method
    headers = request.headers
    content_length = request.content_length
    app = self.app
    response:Response|None = None
    try: # Outer: bare responses for body read failures and unhandled application errors, including a failing app hook.
      try: # Inner: ResponseError, BodyTooLargeError, NotImplementedError.
        app.check_request(request)
        request.privileges = app.authenticate(request)
        validate_privileges(request.privileges)
        destination = app.resolve_destination(request)
        check_access(request.privileges, destination.required_privileges)
        handler = destination.get_handler(request)

        if conn.h11_conn.client_is_waiting_for_100_continue:
          expect_response = handler.handle_expect_100_continue(request)
          if expect_response.status == HTTPStatus.CONTINUE:
            self._send_informational_response(conn.h11_conn, conn.socket, expect_response)
            conn.response_sent = True
          else:
            response = expect_response # Reject before the body is sent; the unread body forces a connection close below.

        if response is None:
          handler.prepare_for_request(request)
          response = handler.handle_request(request)

      except ResponseError as exc:
        response = self._error_response(conn, request, exc)
      except BodyTooLargeError:
        response = self._error_response(conn, request, ResponseError(HTTPStatus.CONTENT_TOO_LARGE, 'Content Too Large'))
        #^ The unread remainder of the body forces a connection close below.
      except NotImplementedError as exc:
        logE('Not implemented.', exc=exc, client_addr=conn.client_addr, method=method, path=request.raw_path)
        response = self._error_response(conn, request, ResponseError(HTTPStatus.NOT_IMPLEMENTED, 'Not Implemented'))
        #^ The fixed reason does not leak the exception message.
      if response.status == HTTPStatus.UNAUTHORIZED and 'www-authenticate' not in response.headers:
        if challenge := app.www_authenticate_for(request): response.headers['www-authenticate'] = challenge
      original_body = response.body
      try:
        response = app.finish_response(request, response)
      finally:
        if response.body is not original_body: close_response_body(original_body)
        #^ Covers a replaced body whether the hook returned a new response, mutated the input, or raised after mutating.
    except ClientProtocolError as exc:
      if response is not None: close_response_body(response.body)
      if conn.h11_conn.trailing_data[1]: raise # The client closed its end and has most likely gone; there is no one to answer.
      response = self._bare_response(exc.status, method=method).set_connection_close()
    except Exception as exc:
      if response is not None: close_response_body(response.body)
      logE('Unhandled application exception.', exc=exc, client_addr=conn.client_addr, method=method, path=request.raw_path)
      response = self._bare_response(HTTPStatus.INTERNAL_SERVER_ERROR, method=method).set_connection_close()

    # Empty requests have a pending EndOfMessage even when the handler has no reason to read a body.
    # Consume it after dispatch rather than before: next_data asserts SEND_BODY, so consuming earlier would break
    # a handler that explicitly reads the empty body.
    if conn.h11_conn.their_state is h11_SEND_BODY and 'transfer-encoding' not in headers and content_length in (None, 0):
      conn.stage = 'request_completion'
      completion = conn.next_event() # Empty framing guarantees completion without a socket read.
      if not isinstance(completion, h11_EndOfMessage):
        raise HttpStateError(f'Expected EndOfMessage for empty request; received: {type(completion).__name__}.')

    # An unconsumed EndOfMessage prevents reuse, including when application dispatch raises ResponseError.
    if conn.h11_conn.their_state is h11_SEND_BODY: response.set_connection_close()
    return response


  def _error_response(self, conn:_Conn, request:Request, error:ResponseError) -> Response:
    '''
    Render an expected application error with the app's `error_response`, or with the built-in plain text renderer
    if the hook returns None or raises. A raise is logged, so a broken hook degrades the format of the response
    rather than its status.
    '''
    try: response = self.app.error_response(request, error)
    except ClientProtocolError: raise
    except Exception as exc:
      logE('error_response hook failed; deferring.', exc=exc, client_addr=conn.client_addr, method=request.method,
        path=request.raw_path)
      response = None
    return response if response is not None else render_error_text(request, error)


  def _bare_response(self, status:HTTPStatus, *, method:str) -> Response:
    'Return a plain text response containing the standard reason phrase, without consulting the app.'
    body = status.phrase if may_send_body(method, status) else None
    return Response(status, body=body, media_type='text/plain')


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

    conn.response_sent = True
    conn.response_status = int(response.status)

    if may_send_body(method, response.status):
      body = response.body
      if isinstance(body, BufferedReader):
        self._send_body_file(h11_conn, socket, body)
      elif body:
        socket.sendall(h11_conn.send(h11_Data(data=cast(bytes, body))))
        #^ bytearray is bytes-like; h11.Data is documented to accept any bytes-like object despite the type being `bytes`.

    socket.sendall(h11_conn.send(h11_EndOfMessage()))


  def _send_body_file(self, h11_conn:h11_Connection, socket:Socket, file:BufferedReader) -> None:
    while True:
      chunk = file.read(self.config.recv_size)
      if not chunk: break
      socket.sendall(h11_conn.send(h11_Data(data=chunk)))
