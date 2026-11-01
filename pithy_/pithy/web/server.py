# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections import deque, OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass, field
from errno import EMFILE, ENFILE, ENOBUFS, ENOMEM, ENOTCONN
from http import HTTPStatus
from io import BufferedReader
from math import inf, isfinite
from os import _exit as os_exit
from queue import Empty as QueueEmpty, LifoQueue, SimpleQueue
from resource import getrlimit, RLIM_INFINITY, RLIMIT_NOFILE, setrlimit
from selectors import DefaultSelector, EVENT_READ, EVENT_WRITE
from socket import AF_INET, SHUT_WR, SO_REUSEADDR, SOCK_STREAM, socket as Socket, socketpair, SOL_SOCKET
from sys import _current_frames
from threading import BoundedSemaphore, current_thread, Event, get_ident, Lock, Thread
from time import monotonic
from traceback import clear_frames, format_stack
from typing import cast, Literal
from urllib.parse import urlsplit as url_split

from h11 import (Connection as h11_Connection, ConnectionClosed as h11_ConnectionClosed, Data as h11_Data, DONE as h11_DONE,
  EndOfMessage as h11_EndOfMessage, Event as h11_Event, IDLE as h11_IDLE, InformationalResponse as h11_InformationalResponse,
  NEED_DATA as h11_NEED_DATA, PAUSED as h11_PAUSED, RemoteProtocolError as h11_RemoteProtocolError, Request as h11_Request,
  Response as h11_Response, SEND_BODY as h11_SEND_BODY, SERVER as h11_SERVER)
from pithy.logs import log, logE, logI, LogLevel, logW

from ..http import http_method_bytes_to_strs, may_send_body
from .app import WebApp
from .auth import AuthenticationResult, check_access
from .env import web_host, web_port
from .errorrender import render_error_text
from .errors import ResponseError
from .request import AddrPair, Request, RequestConn
from .requestconn import BodyAlreadyReadError, BodyTooLargeError, ClientProtocolError
from .response import close_response_body, Response


_context_keywords_ = ['access logging', 'connection draining', 'h11', 'http 1.1', 'http.server', 'keep alive', 'multithreading',
  'request dispatch', 'socket', 'thread pool', 'watchdog', 'worker duration']


BAD_REQUEST = HTTPStatus.BAD_REQUEST

accept_pause = 0.1
'Seconds to stop accepting connections after accept fails for lack of descriptors or kernel memory.'

default_max_connections = 1024
'The connection cap used when `ServerConfig.max_connections` is unset, reduced if necessary to fit the descriptor limit.'

fd_reserve = 64
'''
Descriptors kept free of connections when sizing the connection cap against the soft RLIMIT_NOFILE limit.
They cover the listener, the wakeup pair, the selector, and files that the application opens.
'''

max_handed_off_files = fd_reserve // 2
'''
The maximum number of open file bodies held by the sender thread.
Connection sizing allows for one descriptor per connection, so these files must fit within `fd_reserve`.
Further file responses are sent by their workers.
'''

deadline_scan_interval = 0.25
'Seconds between checks of the header deadlines in the listener thread, and of the send deadlines in the sender thread.'

_accept_exhaustion_errnos = frozenset({EMFILE, ENFILE, ENOBUFS, ENOMEM})


type _WorkerPhase = Literal['request_headers', 'application', 'request_body', 'response', 'cleanup']
'What a worker is currently doing, as shown in duration reports. Only `application` runs application code.'

type _ConnStage = Literal['request_headers', 'request_body', 'request_completion', 'drain_body']
'The most recent read stage of a connection, recorded in protocol failure logs.'


class HttpStateError(Exception):
  'Raised when H11 is in an unexpected state.'


@dataclass(slots=True)
class _WorkerState:
  '''
  The state of a worker while it handles one connection assignment. It is discarded when the worker finishes the assignment.

  `worker_exit_after` applies only to the `application` phase, when the worker is running application code.
  In the other phases the worker is doing client IO, and the slow client limits end any long waits.
  '''

  name:str
  client_addr:AddrPair
  started:float
  phase_started:float
  lock:Lock
  'The shared `WebServer._monitoring_lock`; protects consistent updates and reads of the worker state.'
  phase:_WorkerPhase = 'request_headers'
  method:str = ''
  path:str = ''
  warned:bool = False


@dataclass(slots=True)
class _ResponseSend:
  '''
  The progress of sending one framed response. Exactly one thread owns this at a time: a worker, then possibly the sender.

  A slow client mitigation limits the total time to `timeout + bytes_sent / min_rate`.
  It does not retain the response or the request, because the sender can hold this for a long time.
  '''

  conn:_Conn
  status:int
  head_len:int
  buffers:deque[memoryview]
  body:bytes|None
  'A `bytes`-like body until it is framed, which happens after the head is sent.'
  file:BufferedReader|None
  'The file while it still has unread bytes.'
  file_to_close:BufferedReader|None
  chunk_size:int
  timeout:float
  min_rate:float
  started:float = 0.0
  last_progress:float = 0.0
  sent:int = 0
  ended:bool = False
  'Whether the end of the message has been framed.'
  charge:int = 0
  'The bytes reserved against `ServerConfig.send_buffer_limit`.'
  access_fields:dict[str,object]|None = None
  access_start:float = 0.0


  @classmethod
  def frame(cls, conn:_Conn, response:Response, method:str, *, chunk_size:int, timeout:float, min_rate:float) -> _ResponseSend:
    'Frame the response head. The body is framed after the head is sent, so that a framing error follows a sent status.'
    event = h11_Response(status_code=response.status.value, headers=response.headers_bytes_list(), reason=response.reason)
    head = conn.h11_conn.send(event)
    body = response.body if may_send_body(method, response.status) else None
    file = body if isinstance(body, BufferedReader) else None
    #^ bytearray is bytes-like; h11.Data is documented to accept any bytes-like object despite the type being `bytes`.
    bytes_body = None if isinstance(body, BufferedReader) or not body else cast(bytes, body)
    file_to_close = response.body if isinstance(response.body, BufferedReader) else None
    return cls(conn=conn, status=int(response.status), head_len=len(head), buffers=deque((memoryview(head),)), body=bytes_body,
      file=file, file_to_close=file_to_close, chunk_size=chunk_size, timeout=timeout, min_rate=min_rate)


  @property
  def deadline(self) -> float:
    'The time at which the client has fallen below the minimum rate, or has stalled.'
    return min(self.started + self.timeout + self.sent / self.min_rate, self.last_progress + self.timeout)


  def send_blocking(self) -> None:
    'Send everything that remains on a socket with a timeout, raising TimeoutError if the client is too slow.'
    if self.file is not None: self.started = self.last_progress = monotonic()
    while (buffer := self._next_buffer()) is not None:
      if self.file is not None:
        self.last_progress = monotonic() # `conn_timeout` limits each send, so only the total can expire here.
        if self.last_progress >= self.deadline: raise TimeoutError('Minimum send rate not met.')
      self.conn.socket.sendall(buffer)
      self.buffers.popleft()
      self._note_sent(len(buffer))


  def try_send_now(self, limit:int) -> bool:
    'Send up to about `limit` bytes without blocking. Returns whether the response is finished.'
    self.started = self.last_progress = monotonic()
    socket = self.conn.socket
    socket.setblocking(False)
    try:
      while self.sent < limit:
        if not self.send_some(): return True
    except BlockingIOError: pass
    finally: socket.settimeout(self.timeout)
    return self._next_buffer() is None


  def send_some(self) -> bool:
    'Make one send on a non-blocking socket. Returns False if nothing remains; raises BlockingIOError if the socket is full.'
    if (buffer := self._next_buffer()) is None: return False
    count = self.conn.socket.send(buffer)
    if count == len(buffer): self.buffers.popleft()
    else: self.buffers[0] = buffer[count:]
    self._note_sent(count)
    self.last_progress = monotonic()
    return True


  def _next_buffer(self) -> memoryview|None:
    'Return the next nonempty buffer, reading from the file if necessary, or None if the response is finished.'
    while True:
      while self.buffers:
        if self.buffers[0]: return self.buffers[0]
        self.buffers.popleft()
      h11_conn = self.conn.h11_conn
      if (body := self.body) is not None:
        self.body = None
        self.buffers.append(memoryview(h11_conn.send(h11_Data(data=body))))
      elif self.file is not None and (chunk := self.file.read(self.chunk_size)):
        self.buffers.append(memoryview(h11_conn.send(h11_Data(data=chunk))))
      elif self.ended: return None
      else:
        self.file = None
        self.ended = True
        self.buffers.append(memoryview(h11_conn.send(h11_EndOfMessage())))


  def _note_sent(self, count:int) -> None:
    previous = self.sent
    self.sent += count
    if previous < self.head_len <= self.sent:
      self.conn.response_sent = True
      self.conn.response_status = self.status


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
  read_timeout:float
  'The timeout for one blocking read or send. It is also the read budget that each request starts with.'
  min_read_rate:float
  'Each byte received adds `1 / min_read_rate` seconds to the read budget; see `_recv_within_budget`.'
  read_credit:float = 0.0
  'The remaining read budget of the current request, in seconds.'
  idle_since:float = field(default_factory=monotonic)
  'Start of the current wait for a request, reset by the listener thread when it registers a returned connection.'
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
  Once set, the connection is closed after the current cycle. A read timeout before any request bytes is not a failure.
  h11 exceptions are replaced because their messages embed received bytes; the replacement is constructed outside of
  the handling block so that it carries no reference to the original.
  Body and completion reads raise it, so its traceback can refer to the frames that hold the request;
  the traceback is cleared at the end of each cycle.
  '''
  response_status:int|None = None # Set once final response headers have been sent.
  worker_state:_WorkerState|None = None
  pending_send:_ResponseSend|None = None
  'Set by a worker when the rest of the response must go to the sender thread.'
  head_event:h11_Event|None = None
  'The complete request head or connection close, parsed by the listener thread for a worker to take.'
  head_started:float = 0.0
  'When the listener thread received the first bytes of the current request head; zero if it has none.'
  head_bytes:int = 0


  def set_phase(self, phase:_WorkerPhase, request:Request|None=None) -> None:
    'Record the worker phase for monitoring.'
    if (state := self.worker_state) is None: return # Direct connection tests do not run a worker.
    with state.lock:
      state.phase = phase
      state.phase_started = monotonic()
      if request is not None:
        state.method = request.method
        state.path = request.raw_path


  def handle_need_data(self) -> bool:
    '''
    Handle a h11_NEED_DATA event by receiving data from the socket and feeding it to h11.
    Returns True on success, and False on an idle timeout or a failure; a failure also sets and logs `self.error`.
    '''
    try:
      data = self._recv_within_budget()
      self.received_bytes += len(data)
      self.pending_request |= bool(data)
      self.h11_conn.receive_data(data)
      return True
    except TimeoutError:
      if not self.pending_request: return False # No request started; treat it as an idle close.
      status = HTTPStatus.REQUEST_TIMEOUT
    except h11_RemoteProtocolError as exc:
      status = _status_for_h11_error(exc)
    self.fail(ClientProtocolError(status))
    return False


  def read_head_nonblocking(self) -> bool:
    '''
    Listener thread: receive any available bytes of the request head. Returns whether a worker should now take the connection.
    This is a slow client mitigation: a worker never waits for a request head to arrive, except for one that follows
    a pipelined request. Raises OSError if the connection failed.
    '''
    self.socket.setblocking(False)
    try: data = self.socket.recv(self.recv_size)
    except BlockingIOError: return False
    finally: self.socket.settimeout(self.read_timeout)
    self.stage = 'request_headers'
    self.received_bytes += len(data)
    self.head_bytes += len(data)
    self.pending_request |= bool(data)
    if data and not self.head_started: self.head_started = monotonic()
    try: self.h11_conn.receive_data(data)
    except h11_RemoteProtocolError as exc:
      self.fail(ClientProtocolError(_status_for_h11_error(exc)))
      return True
    return self.poll_head()


  def poll_head(self) -> bool:
    'Parse the bytes received so far. Returns whether a complete head, a close or a failure means a worker should take over.'
    self.stage = 'request_headers'
    try: event = self.next_event()
    except ClientProtocolError: return True
    if event is h11_NEED_DATA: return False
    self.head_event = cast(h11_Event, event)
    return True


  @property
  def head_deadline(self) -> float:
    'The time at which the client has fallen below the minimum rate while sending the request head.'
    return self.head_started + self.read_timeout + self.head_bytes / self.min_read_rate


  def _recv_within_budget(self) -> bytes:
    '''
    Receive from the socket, raising TimeoutError once the read budget of the current request is used up.

    This is a slow client mitigation. A per-read timeout alone is not enough,
    because a client can hold a worker indefinitely by sending one byte at a time.
    The budget limits the total time that one request can spend blocked in reads to
    `read_timeout + bytes_received / min_read_rate`.
    Only time blocked in this method counts, so a slow handler does not use up the budget of its client.
    '''
    if self.read_credit <= 0: raise TimeoutError('Read budget exhausted.')
    self.socket.settimeout(min(self.read_timeout, self.read_credit))
    start = monotonic()
    try: data = self.socket.recv(self.recv_size)
    finally:
      self.read_credit -= monotonic() - start
      self.socket.settimeout(self.read_timeout)
    self.read_credit += len(data) / self.min_read_rate
    return data


  def limit_reads_to(self, timeout:float) -> None:
    'Limit all further reads to `timeout` seconds in total. Received bytes do not add to the budget.'
    self.read_timeout = self.read_credit = timeout
    self.min_read_rate = inf


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
    Returns the next Request, or None when the client closed the connection.
    A read failure also returns None and sets `self.error`; malformed request headers raise ClientProtocolError.
    Idle timeouts are enforced by the listener, which only hands readable connections to workers.
    A read timeout before any request bytes arrive therefore indicates a spurious wakeup;
    it also returns None, without an error.
    '''
    self.stage = 'request_headers'
    self.read_credit = self.read_timeout # Headers read here and the body of one request share a budget.
    if self.error is not None: return None # The listener thread found a failure.
    assert self.head_event is not None or self.h11_conn.our_state is h11_IDLE # Parsing the head advances the state.
    while True:
      event = self.head_event or self.next_event()
      self.head_event = None
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
        # While a handler waits for its request body, the worker is waiting on the client. See `worker_exit_after`.
        if self.stage == 'request_body': self.set_phase('request_body')
        ok = self.handle_need_data()
        if self.stage == 'request_body': self.set_phase('application')
        if ok: continue
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
      self.head_started = 0.0
      self.head_bytes = 0
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


def _resolve_max_connections(max_connections:int|None, *, raise_fd_limit:bool) -> int:
  '''
  Return the connection cap, checked against the soft RLIMIT_NOFILE limit with `fd_reserve` descriptors to spare.
  See `ServerConfig.max_connections` and `ServerConfig.raise_fd_limit` for the policy.
  Raising never sets the soft limit to infinity; it stops at what the cap needs, or at the hard limit.
  '''
  if max_connections is not None and max_connections < 1:
    raise ValueError(f'max_connections must be positive; received {max_connections}.')
  target = default_max_connections if max_connections is None else max_connections
  needed = target + fd_reserve
  soft, hard = getrlimit(RLIMIT_NOFILE)
  if _limit_fits(soft, needed): return target
  if raise_fd_limit:
    raised = needed if _limit_fits(hard, needed) else hard
    try: setrlimit(RLIMIT_NOFILE, (raised, hard))
    except (OSError, ValueError) as exc:
      raise ValueError(f'Could not raise the soft descriptor limit from {soft} to {raised}: {exc}') from exc
    soft = raised
    if soft >= needed: return target
  if max_connections is None and soft > fd_reserve: return soft - fd_reserve
  hard_desc = 'unlimited' if hard == RLIM_INFINITY else hard
  raise ValueError(f'max_connections={target} needs {needed} file descriptors, but the soft limit is {soft} '
    f'(hard limit: {hard_desc}); raise it with `ulimit -n` or LimitNOFILE, set raise_fd_limit, or lower max_connections.')


def _limit_fits(limit:int, needed:int) -> bool:
  'Whether a resource limit allows `needed`. RLIM_INFINITY is a large value on macOS but -1 on Linux, so test it explicitly.'
  return limit == RLIM_INFINITY or limit >= needed


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
  conn_timeout: the timeout in seconds for each blocking operation on connections with a request in progress.
    Also the initial read budget of each request; see `min_read_rate`.
  min_read_rate: the minimum rate in bytes per second that a client must sustain while sending a request.
    This is a slow client mitigation. The listener thread applies this limit while it collects the request head,
    and the worker applies it again while reading the body. Each is limited to `conn_timeout + bytes_received / min_read_rate`.
    h11 limits the size of request headers, so their read time is limited too.
    The handler's size limit does the same for bodies.
  idle_timeout: the time in seconds that a connection may wait for its next request, or its first, before it is closed.
  drain_timeout: the total time in seconds to spend draining an unread request body before closing a connection.
  drain_max_bytes: the maximum number of unread request body bytes to drain before closing a connection.
  min_send_rate: the minimum rate in bytes per second that a client must sustain while receiving a response.
    This is a slow client mitigation. The time to send one file response or handed off response is limited to
    `conn_timeout + bytes_sent / min_send_rate`, and it fails if `conn_timeout` passes with no progress.
  send_buffer_limit: the maximum total bytes of responses held in memory by the sender thread.
    A response that does not fit is sent by its worker instead.
  max_connections: the maximum number of open client connections, including idle ones.
    At capacity, a new connection replaces the longest idle connection, or is dropped if none is idle.
    None selects `default_max_connections`, reduced if necessary to fit the soft descriptor limit
    with `fd_reserve` descriptors to spare. An explicit value that does not fit raises ValueError.
  raise_fd_limit: whether to raise the soft descriptor limit of the process toward the hard limit so that
    the connection cap fits. The limit is process-wide and inherited by child processes.
  num_threads: the number of worker threads, which bounds the number of requests handled concurrently.
    A worker is occupied while it reads a request and runs its handler, but not between requests.
    It is also occupied while sending a response if the sender thread is at capacity.
  worker_warn_after: the seconds that a worker can spend on one assignment before a warning with a stack trace is logged.
    None disables warnings. This is a diagnostic for any cause of slowness.
    It covers every phase of the assignment, but not time waiting in the queue.
    Each assignment warns once. A warning means that the assignment is slow, not necessarily that the worker is hung.
  worker_exit_after: the seconds that a worker can run application code without interruption before the server logs an error
    and exits the entire process with status 1. None disables this policy.
    This is for application hang recovery. A hung thread cannot be cancelled and would occupy its worker permanently,
    so the only remedy is for a supervisor to restart the process.
    Client IO does not count and restarts the clock. This includes body reads made by a handler.
    A slow client therefore cannot trigger an exit, but a request that makes a handler legitimately slow can.
    Set this above the longest application timeout. Forced exit bypasses application cleanup.
    Both thresholds must be finite and positive when enabled. Checks continue during shutdown, at intervals of at most
    one second, provided Python threads can still execute.
  recv_size: the maximum number of bytes to receive at once from client connections.
  log_access: whether to log each parsed HTTP request after response sending completes or fails.
    Access fields are c (client), u (uid from request.ctx, default 0), m (method), p (path), q (raw query), s (status),
    and d (duration).
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
  idle_timeout:float = 5.0
  drain_timeout:float = 1.0
  drain_max_bytes:int = 1 << 20
  min_read_rate:float = 1024.0
  min_send_rate:float = 1024.0
  send_buffer_limit:int = 1 << 26
  num_threads:int = 8
  worker_warn_after:float|None = 30.0
  worker_exit_after:float|None = None
  max_connections:int|None = None
  raise_fd_limit:bool = False
  thread_name_prefix:str = 'WebServer'
  log_access:bool = True
  startup_message:str = ''
  prevent_client_caching:bool = False


  def __post_init__(self) -> None:
    for name, rate in (('min_read_rate', self.min_read_rate), ('min_send_rate', self.min_send_rate)):
      if not isfinite(rate) or rate <= 0:
        raise ValueError(f'{name} must be finite and positive; received: {rate!r}.')
    if self.send_buffer_limit < 0:
      raise ValueError(f'send_buffer_limit must not be negative; received: {self.send_buffer_limit!r}.')
    for name, value in (('worker_warn_after', self.worker_warn_after), ('worker_exit_after', self.worker_exit_after)):
      if value is not None and (not isfinite(value) or value <= 0):
        raise ValueError(f'{name} must be finite and positive, or None; received: {value!r}.')


class WebServer:
  '''
  WebServer is a multithreaded HTTP 1.1 server.
  A selector holds idle connections, including speculative connections with no request yet, without occupying workers.
  The listener also collects each request head, so that a worker is only assigned once there is a request to handle.
  Workers handle one request at a time and return reusable connections to the selector.
  Readable connections wait for workers in a LIFO queue, on the assumption that under load it is better to serve some requests
  quickly and let others time out, rather than have all requests delayed or time out.
  A worker sends what it can of a response without blocking, then passes the rest to a single sender thread.
  A slow download therefore holds a connection slot and not a worker.
  The sender runs no application code, and it reads files on its own thread so that a slow disk only delays other downloads.

  The server's limits address three different causes of failure. Code that enforces a limit names its cause:
  * Slow client mitigation: clients are untrusted, so a slow client should lose its own connection without affecting others.
    The server closes the connection when a client falls below `min_read_rate` or `min_send_rate`, or stalls for `conn_timeout`.
    A slow client can occupy a worker only while sending a request body to a handler, or when the sender is at capacity.
    Each connection is limited separately, so public deployments also need per-client limits in a reverse proxy.
  * Application hang recovery: application code is trusted but can have bugs, and a hung thread cannot be cancelled.
    `worker_warn_after` logs slow workers. `worker_exit_after` exits the process so that a supervisor can restart it.
  * Environment failure: if logging raises, the process can no longer report its state.
    It exits so that a supervisor can restart it with new descriptors.
    If logging blocks, each thread that logs waits until it unblocks, so a brief stall recovers on its own.
    The watchdog waits too, so a permanent stall requires an external liveness check.
  '''

  def __init__(self, *, app:WebApp, config:ServerConfig=ServerConfig()) -> None:
    '''
    Initialize the web server.
    The server will bind to the host and port specified in the config.
    If port 0 was specified then the dynamically assigned port is saved in `self.port`.
    The connection cap is resolved against the descriptor limit and saved in `self.max_connections`.
    '''

    self.app = app
    self.config = config
    self.max_connections = _resolve_max_connections(config.max_connections, raise_fd_limit=config.raise_fd_limit)
    self._stop = Event()
    self._lock = Lock()  # Guards _serving, which decides whether shutdown() or serve_forever() closes the sockets.
    self._serving = False
    self._wakeup_reader, self._wakeup_writer = socketpair()
    self._wakeup_reader.setblocking(False)
    self._wakeup_writer.setblocking(False)
    self._conn_queue: LifoQueue[_Conn|None] = LifoQueue() # Bounded by the connection slots.
    self._idle_queue: SimpleQueue[_Conn] = SimpleQueue()
    # A connection owns its slot across selector, queue and worker handoffs, until its socket is closed.
    self._conn_slots = BoundedSemaphore(self.max_connections)
    self._workers: list[Thread] = []
    self._sender:Thread|None = None
    self._send_queue:SimpleQueue[_ResponseSend] = SimpleQueue()
    self._send_stop = Event() # Set only after the workers have exited, so that no more sends can arrive.
    self._send_wakeup_reader, self._send_wakeup_writer = socketpair()
    self._send_wakeup_reader.setblocking(False)
    self._send_wakeup_writer.setblocking(False)
    self._send_lock = Lock() # Guards the two reservation totals below.
    self._reserved_send_bytes = 0
    self._reserved_send_files = 0
    self._monitoring_lock = Lock()
    '''Protect `_active_workers` and its worker states with short critical sections.

    This lock is non-reentrant. Do not acquire other locks, wait on queues, perform IO, format stacks, log or call
    application code while holding it. Do not call `_Conn.set_phase` while holding it; that method acquires this lock.
    '''
    self._active_workers:dict[int,_WorkerState] = {}
    thresholds = [t for t in (config.worker_warn_after, config.worker_exit_after) if t is not None]
    self._worker_check_interval = min(1.0, *thresholds) if thresholds else None

    socket = Socket(AF_INET, SOCK_STREAM)
    self._socket = socket
    socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    socket.bind((config.host, config.port))
    socket.listen(config.backlog)
    socket.setblocking(False)
    #^ On macOS accepted sockets inherit the non-blocking flag; the accept loop resets it with settimeout.

    self.scheme = 'http'
    self.host = config.host
    self.port = (config.port or socket.getsockname()[1])


  @property
  def url(self) -> str:
    return f'{self.scheme}://{self.host}:{self.port}'


  def serve_forever(self) -> None:
    'Starts the server loop; call shutdown() from another thread to stop the server and then this method will return.'
    cfg = self.config
    logI('Serving.', url=self.url, max_connections=self.max_connections)
    if cfg.startup_message: logI(cfg.startup_message)

    for i in range(cfg.num_threads):
      thread = Thread(target=self._worker, daemon=False, name=f'{cfg.thread_name_prefix}-worker-{i}')
      thread.start()
      self._workers.append(thread)
    try:
      with self._lock:
        if self._stop.is_set(): return  # shutdown() was called first and has already closed the sockets.
        self._serving = True
      self._sender = Thread(target=self._send_loop, daemon=False, name=f'{cfg.thread_name_prefix}-sender')
      self._sender.start()
      with DefaultSelector() as selector:
        selector.register(self._wakeup_reader, EVENT_READ)
        selector.register(self._socket, EVENT_READ)
        idle:OrderedDict[Socket,_Conn] = OrderedDict()
        partial:dict[Socket,_Conn] = {} # Connections with an incomplete request head; these are not evicted at capacity.
        next_head_scan = 0.0
        # Only this thread stamps idle_since, immediately before insertion, so the front entry is always the next to expire.
        # OrderedDict rather than dict: repeatedly removing the front of a dict scans past deleted slots.
        accept_resume:float|None = None # Set while accepting is paused after descriptor exhaustion.
        try:
          while not self._stop.is_set():
            self._check_workers()
            if accept_resume is not None and monotonic() >= accept_resume:
              selector.register(self._socket, EVENT_READ)
              accept_resume = None
            while True:
              try: conn = self._idle_queue.get_nowait()
              except QueueEmpty: break
              if conn.h11_conn.trailing_data[0]: # A pipelined request may already be buffered in h11.
                if conn.poll_head(): self._conn_queue.put(conn)
                else:
                  conn.head_started = monotonic()
                  partial[conn.socket] = conn
                  selector.register(conn.socket, EVENT_READ, conn)
              else:
                conn.idle_since = monotonic()
                idle[conn.socket] = conn
                selector.register(conn.socket, EVENT_READ, conn)
            deadline = next(iter(idle.values())).idle_since + cfg.idle_timeout if idle else None
            if accept_resume is not None: deadline = accept_resume if deadline is None else min(deadline, accept_resume)
            if self._worker_check_interval is not None:
              check_deadline = monotonic() + self._worker_check_interval
              deadline = check_deadline if deadline is None else min(deadline, check_deadline)
            if partial:
              scan_deadline = monotonic() + deadline_scan_interval
              deadline = scan_deadline if deadline is None else min(deadline, scan_deadline)
            ready = selector.select(None if deadline is None else max(0, deadline - monotonic()))
            if self._stop.is_set(): break
            # Handle connection events before the listener, so that a readable connection leaves `idle` before a new
            # connection at capacity replaces the longest idle one. The stable sort moves only the listener.
            for key, _ in sorted(ready, key=lambda event: event[0].fileobj is self._socket):
              if key.fileobj is self._wakeup_reader:
                try: self._wakeup_reader.recv(65536)
                except BlockingIOError: pass
              elif key.fileobj is self._socket:
                try: conn_sock, client_addr = self._socket.accept()
                except (BlockingIOError, ConnectionAbortedError): continue # The pending connection was reset before accept.
                except OSError as exc:
                  if exc.errno not in _accept_exhaustion_errnos: raise
                  # Linux leaves the pending connection in the backlog, so the listener stays readable.
                  # Pause to avoid spinning. macOS closes the pending connection instead.
                  logE('Accept failed for lack of resources; pausing.', exc=exc, pause=accept_pause)
                  selector.unregister(self._socket)
                  accept_resume = monotonic() + accept_pause
                  continue
                if not self._conn_slots.acquire(blocking=False):
                  if not idle:
                    logI('Connection capacity reached with no idle connections; dropping connection.', client_addr=client_addr)
                    conn_sock.close()
                    continue
                  # Transfer the slot of the longest idle connection; a browser reconnects transparently.
                  idle_socket, _ = idle.popitem(last=False)
                  selector.unregister(idle_socket)
                  idle_socket.close()
                conn_sock.settimeout(cfg.conn_timeout)
                conn = _Conn(client_addr=client_addr, socket=conn_sock, h11_conn=h11_Connection(h11_SERVER),
                  recv_size=cfg.recv_size, read_timeout=cfg.conn_timeout, min_read_rate=cfg.min_read_rate)
                idle[conn_sock] = conn
                selector.register(conn_sock, EVENT_READ, conn)
              else:
                conn = cast(_Conn, key.data)
                conn_sock = conn.socket
                if conn_sock not in idle and conn_sock not in partial: continue # Closed; not expected given the ordering above.
                try: ready_for_worker = conn.read_head_nonblocking()
                except OSError as exc: # The client has gone.
                  logI('Connection read error.', exc=exc, client_addr=conn.client_addr)
                  idle.pop(conn_sock, None)
                  partial.pop(conn_sock, None)
                  selector.unregister(conn_sock)
                  conn_sock.close()
                  self._conn_slots.release()
                  continue
                if ready_for_worker:
                  idle.pop(conn_sock, None)
                  partial.pop(conn_sock, None)
                  selector.unregister(conn_sock)
                  self._conn_queue.put(conn)
                elif conn.pending_request and idle.pop(conn_sock, None) is not None:
                  partial[conn_sock] = conn
            now = monotonic()
            if partial and now >= next_head_scan:
              next_head_scan = now + deadline_scan_interval
              for conn in [conn for conn in partial.values() if now >= conn.head_deadline]:
                # Slow client mitigation: a worker answers with 408 and closes the connection.
                conn.fail(ClientProtocolError(HTTPStatus.REQUEST_TIMEOUT))
                del partial[conn.socket]
                selector.unregister(conn.socket)
                self._conn_queue.put(conn)
            while idle:
              socket, conn = next(iter(idle.items()))
              if now - conn.idle_since < cfg.idle_timeout: break
              del idle[socket]
              selector.unregister(socket)
              socket.close()
              self._conn_slots.release()
        finally:
          for socket in (*idle, *partial):
            socket.close()
            self._conn_slots.release()
    except KeyboardInterrupt:
      logI('Interrupted.')
    finally:
      with self._lock:
        self._stop.set()
      for _ in self._workers: self._conn_queue.put(None)  # Signal each worker to exit.
      for thread in self._workers:
        while thread.is_alive():
          thread.join(timeout=self._worker_check_interval)
          self._check_workers()
      if self._sender is not None:
        self._send_stop.set()
        self._wake_sender()
        self._sender.join()
      for queue in (self._conn_queue, self._idle_queue):
        while True:
          try: pending = queue.get_nowait()
          except QueueEmpty: break
          if pending is not None:
            pending.socket.close()
            self._conn_slots.release()
      with self._lock:
        self._serving = False
        self._close_sockets()


  def shutdown(self) -> None:
    '''
    Request shutdown, waking the accept loop immediately. Active requests finish before serve_forever returns.
    Responses held by the sender thread get `conn_timeout` more to finish, and are then abandoned.

    Closing a listening socket from another thread does not reliably wake accept on Unix, so a socket pair is used instead.
    If serve_forever is not running then the sockets are closed here, so that a server that never served does not leak them.
    '''
    with self._lock:
      if self._stop.is_set(): return
      self._stop.set()
      if self._serving: self._wake_listener()
      else: self._close_sockets()


  def _wake_listener(self) -> None:
    'Notify the selector of returned connections or shutdown. A full buffer already guarantees a wakeup.'
    try: self._wakeup_writer.send(b'\0')
    except BlockingIOError: pass


  def _wake_sender(self) -> None:
    'Notify the sender of new sends or shutdown. A full buffer already guarantees a wakeup.'
    try: self._send_wakeup_writer.send(b'\0')
    except BlockingIOError: pass


  def _close_sockets(self) -> None:
    'Close the listener and the wakeup pairs; safe to call repeatedly.'
    self._socket.close()
    self._wakeup_reader.close()
    self._wakeup_writer.close()
    self._send_wakeup_reader.close()
    self._send_wakeup_writer.close()


  def _worker(self) -> None:
    'Worker thread entry point.'
    while True:
      conn = self._conn_queue.get()
      if conn is None: break
      ident = get_ident()
      now = monotonic()
      state = _WorkerState(current_thread().name, conn.client_addr, now, now, self._monitoring_lock)
      with self._monitoring_lock:
        self._active_workers[ident] = conn.worker_state = state
      try:
        try:
          reusable = not self._stop.is_set() and self._handle_connection(conn)
          send = conn.pending_send
          if not reusable and send is None:
            conn.set_phase('cleanup')
            self._close_connection(conn)
            self._conn_slots.release()
        finally:
          with self._monitoring_lock:
            del self._active_workers[ident]
            conn.worker_state = None
        if send is not None: # The sender takes ownership only after this worker has finished with the connection.
          self._send_queue.put(send)
          self._wake_sender()
        elif reusable:
          self._idle_queue.put(conn)
          self._wake_listener()
      except BaseException as exc:
        try: logE('Uncaught worker exception; exiting process.', exc=exc, client_addr=conn.client_addr)
        finally: os_exit(1) # Environment failure: exit even if logging raises. Otherwise the thread would end with no record.


  def _send_loop(self) -> None:
    'Sender thread entry point: finish sending the responses handed off by workers.'
    try:
      with DefaultSelector() as selector:
        selector.register(self._send_wakeup_reader, EVENT_READ)
        active:dict[Socket,_ResponseSend] = {}
        grace_end:float|None = None
        while True:
          while True:
            try: send = self._send_queue.get_nowait()
            except QueueEmpty: break
            send.conn.pending_send = None
            send.conn.socket.setblocking(False)
            active[send.conn.socket] = send
            selector.register(send.conn.socket, EVENT_WRITE, send)
          if self._send_stop.is_set():
            if not active: break
            if grace_end is None: grace_end = monotonic() + self.config.conn_timeout
          for key, _ in selector.select(deadline_scan_interval if active else None):
            if key.fileobj is self._send_wakeup_reader:
              try: self._send_wakeup_reader.recv(65536)
              except BlockingIOError: pass
              continue
            send = cast(_ResponseSend, key.data)
            try:
              if send.send_some(): continue
              ok = True
            except BlockingIOError: continue
            except OSError as exc: # The client has gone.
              logI('Response send failed.', exc=exc, client_addr=send.conn.client_addr)
              ok = False
            except Exception as exc:
              logE('Response send error.', exc=exc, client_addr=send.conn.client_addr)
              ok = False
            selector.unregister(send.conn.socket)
            del active[send.conn.socket]
            self._finish_send(send, ok=ok)
          now = monotonic()
          for send in [send for send in active.values() if now >= send.deadline or (grace_end and now >= grace_end)]:
            # Slow client mitigation: the client loses its connection. A shutdown can also end the grace period.
            logI('Response send timed out.', client_addr=send.conn.client_addr, sent=send.sent)
            selector.unregister(send.conn.socket)
            del active[send.conn.socket]
            self._finish_send(send, ok=False)
    except BaseException as exc:
      try: logE('Uncaught sender exception; exiting process.', exc=exc)
      finally: os_exit(1) # Environment failure: exit even if logging raises. Otherwise the thread would end with no record.


  def _finish_send(self, send:_ResponseSend, *, ok:bool) -> None:
    'Release the resources of a handed off response, log access, and then reuse or close the connection.'
    conn = send.conn
    if send.file_to_close is not None: close_response_body(send.file_to_close)
    with self._send_lock:
      self._reserved_send_bytes -= send.charge
      if send.file_to_close is not None: self._reserved_send_files -= 1
    if send.access_fields is not None:
      logI('access', **send.access_fields, s=conn.response_status if conn.response_status is not None else 0,
        d=round(monotonic() - send.access_start, 3))
    if ok and not self._stop.is_set() and conn.recycle():
      conn.socket.settimeout(conn.read_timeout)
      self._idle_queue.put(conn)
      self._wake_listener()
    else:
      try: conn.socket.close() # The request was completely read, so there is no body to drain.
      except OSError: pass
      self._conn_slots.release()


  def _reserve_send(self, send:_ResponseSend) -> bool:
    'Reserve memory and a file allowance for a handoff, so that slow clients cannot exhaust either. Returns False if full.'
    charge = sum(len(buffer) for buffer in send.buffers) + (len(send.body) if send.body else 0)
    if send.file is not None: charge += send.chunk_size
    has_file = send.file_to_close is not None
    with self._send_lock:
      if self._reserved_send_bytes + charge > self.config.send_buffer_limit: return False
      if has_file and self._reserved_send_files >= max_handed_off_files: return False
      self._reserved_send_bytes += charge
      if has_file: self._reserved_send_files += 1
    send.charge = charge
    return True


  def _check_workers(self) -> None:
    '''
    The application hang recovery check.
    Warn about long-running requests and exit the process if application code has exceeded `worker_exit_after`.
    It does not hold the monitoring lock while formatting stacks, logging or exiting.
    '''
    warn_after = self.config.worker_warn_after
    exit_after = self.config.worker_exit_after
    if warn_after is None and exit_after is None: return
    reports:list[tuple[int,_WorkerState,bool,dict[str,object]]] = []
    with self._monitoring_lock:
      now = monotonic()
      for ident, state in self._active_workers.items():
        elapsed = now - state.started
        # Count only application time, so that a slow client cannot make the process exit.
        fatal = exit_after is not None and state.phase == 'application' and now - state.phase_started >= exit_after
        if not fatal and (warn_after is None or state.warned or elapsed < warn_after): continue
        state.warned = True
        reports.append((ident, state, fatal, dict(worker=state.name, client_addr=state.client_addr,
          elapsed=round(elapsed, 3), phase=state.phase, method=state.method, path=state.path)))
    for ident, state, fatal, fields in reports:
      frame = _current_frames().get(ident)
      try: fields['stack'] = format_stack(frame) if frame is not None else []
      finally: del frame # Do not retain frames, requests or application locals after reporting.
      with self._monitoring_lock:
        if self._active_workers.get(ident) is not state: continue # Completed or reassigned while formatting the stack.
      try:
        if fatal: logE('Application exceeded duration threshold; exiting process.', **fields)
        else: logW('Worker exceeded duration threshold.', **fields)
      except (OSError, ValueError): fatal = True # Environment failure: stdout is broken or closed; see `WebServer`.
      if fatal: os_exit(1)


  def _handle_connection(self, conn:_Conn) -> bool:
    'Handle one request on a readable connection; return whether it can be reused. The caller owns socket cleanup.'
    try:
      try:
        if event := conn.next_request():
          method = conn.method = http_method_bytes_to_strs.get(event.method, '')
          conn.http_version = event.http_version.decode('ascii') if event.http_version in (b'1.0', b'1.1') else ''
          self._handle_connection_cycle(conn, event, method)
          return conn.pending_send is None and conn.recycle()
      except ClientProtocolError: pass # Logged when detected.
      if conn.error is not None and conn.h11_conn.our_state is h11_IDLE and not conn.h11_conn.trailing_data[1]:
        # Malformed or incomplete request headers from a client that is still connected: answer with a bare response.
        # h11 permits a response before any request. Later failures were answered during the cycle, or the client has closed.
        response = self._bare_response(conn.error.status, method='').set_connection_close()
        try: self._send_response(conn, response=response, method='')
        except OSError: pass # The client has gone.
    except Exception as exc:
      logE('Connection handling error.', exc=exc, client_addr=conn.client_addr)
    return False


  def _handle_connection_cycle(self, conn:_Conn, event:h11_Request, method:str) -> None:
    'Own the request through dispatch, response sending and access logging, releasing it before waiting for another request.'
    start_time = monotonic()
    request:Request|None = None
    try:
      result = self._make_request(conn, event, method)
      if isinstance(result, Request):
        request = result
        conn.set_phase('application', request)
        response = self._handle_request(conn, request)
      else:
        response = result
      body = response.body
      try:
        if self.config.prevent_client_caching: response.set_no_cache_headers()
        self._send_response(conn, response=response, method=method)
      finally:
        conn.set_phase('cleanup')
        if conn.pending_send is None: close_response_body(body) # Otherwise the sender closes it after sending.
    finally:
      try:
        if self.config.log_access:
          fields = self._access_fields(conn, event, request)
          if (send := conn.pending_send) is None:
            logI('access', **fields, s=conn.response_status if conn.response_status is not None else 0,
              d=round(monotonic() - start_time, 3))
          else: # The sender logs when sending finishes. The fields do not retain the request.
            send.access_fields = fields
            send.access_start = start_time
      finally:
        if conn.error is not None: conn.error.__traceback__ = None
        #^ Release the frames of this cycle, including those of the original socket read, which refer to the request.


  def _access_fields(self, conn:_Conn, event:h11_Request, request:Request|None) -> dict[str,object]:
    'The access record fields other than status and duration, taken at the server boundary so that all requests are covered.'
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
    method = event.method.decode('ascii', errors='replace')
    return dict(c=client_addr[0] if client_addr else '-', u=uid, m=method, p=path, q=query)


  def _close_connection(self, conn:_Conn) -> None:
    '''
    Close a client connection, first draining any unread request body.

    Closing a socket whose kernel receive buffer still holds unread data causes the kernel to send an RST instead of a FIN.
    The RST aborts the connection at the client, which fails its remaining sends and can discard response bytes
    that it has not yet read. This turns a well-formed error response (e.g. the 413 that we send when a body exceeds
    the handler limit) into a connection reset error on the client, nondeterministically depending on timing.

    To avoid this we half-close the socket, which tells the client that no more response data is coming
    while still allowing it to finish uploading, and then read the rest of the body before closing.
    Slow client mitigation: the drain is bounded by `drain_max_bytes` and by `drain_timeout` in total,
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
        conn.limit_reads_to(self.config.drain_timeout)
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
        authentication = app.authenticate(request)
        if not isinstance(authentication, AuthenticationResult):
          raise TypeError('authenticate must return an AuthenticationResult.')
        request.is_authenticated = authentication.is_authenticated
        request.privileges = authentication.privileges
        destination = app.resolve_destination(request)
        check_access(request.is_authenticated, request.privileges, destination.required_access)
        handler = destination.get_handler(request)

        if conn.h11_conn.client_is_waiting_for_100_continue:
          expect_response = handler.handle_expect_100_continue(request)
          if expect_response.status == HTTPStatus.CONTINUE:
            conn.set_phase('response') # Sending to the client does not count as application time.
            self._send_informational_response(conn.h11_conn, conn.socket, expect_response)
            conn.set_phase('application')
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
    '''
    Send a response. Under a worker, set `conn.pending_send` if the rest must go to the sender thread.
    Workers send to clients that are slow only if the sender is at capacity, or if the request was not completely read,
    because the connection might then need draining, which blocks.
    '''
    conn.set_phase('response')
    cfg = self.config
    send = _ResponseSend.frame(conn, response, method, chunk_size=cfg.recv_size, timeout=cfg.conn_timeout,
      min_rate=cfg.min_send_rate)
    if conn.worker_state is not None and conn.error is None and conn.h11_conn.their_state is h11_DONE \
     and not self._stop.is_set():
      if send.try_send_now(cfg.recv_size): return
      if self._reserve_send(send):
        conn.pending_send = send
        return
    send.send_blocking()
