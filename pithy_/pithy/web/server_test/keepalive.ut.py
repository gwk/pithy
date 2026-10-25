# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Iterator
from contextlib import contextmanager, ExitStack
from http.client import HTTPConnection
from socket import create_connection, socket as Socket
from threading import current_thread, Event, Thread
from time import monotonic
from unittest.mock import patch

from pithy.web.app import WebApp
from pithy.web.auth import allow_public
from pithy.web.request import Request
from pithy.web.response import Response
from pithy.web.server import ServerConfig, WebServer
from utest import utest_run, utest_val


class App(WebApp):
  started = Event()
  'Set once a request for /block has started.'
  unblock = Event()
  'Requests for /block wait for this event.'

  @allow_public
  def handle_request(self, request:Request) -> Response:
    if request.raw_path == '/block':
      App.started.set()
      App.unblock.wait(timeout=5)
    return Response(body='ok')


@contextmanager
def running_server(*, idle_timeout:float=10, max_connections:int=64) -> Iterator[tuple[WebServer,Thread]]:
  server = WebServer(app=App(), config=ServerConfig(host='127.0.0.1', num_threads=1,
    idle_timeout=idle_timeout, max_connections=max_connections, log_access=False))
  errors:list[BaseException] = []

  def serve() -> None:
    try: server.serve_forever()
    except BaseException as error: errors.append(error)

  with patch('pithy.web.server.logI'):
    thread = Thread(target=serve)
    thread.start()
    try: yield server, thread
    finally:
      server.shutdown()
      thread.join(timeout=3)
      assert not thread.is_alive()
      utest_val([], errors)


@utest_run
def test_idle_connections_release_workers() -> None:
  'Idle keep-alive and speculative connections must not block other clients, even with only one worker.'
  with running_server() as (server, thread), ExitStack() as clients:
    try:
      connections = []
      for _ in range(8):
        conn = HTTPConnection(server.host, server.port, timeout=1)
        clients.callback(conn.close)
        conn.request('GET', '/')
        response = conn.getresponse()
        utest_val(b'ok', response.read())
        utest_val(None, response.getheader('connection'))
        connections.append((conn, conn.sock))
      # Browsers can also connect before sending any request bytes.
      clients.enter_context(create_connection((server.host, server.port), timeout=1))
      for conn, socket in reversed(connections):
        conn.request('GET', '/')
        utest_val(b'ok', conn.getresponse().read())
        utest_val(socket, conn.sock)
      # Shutdown must close parked sockets without waiting for the ten-second idle timeout.
      server.shutdown()
      thread.join(timeout=1)
      utest_val(False, thread.is_alive())
    finally:
      clients.close()
      server.shutdown()
      thread.join(timeout=3)
      assert not thread.is_alive()


@utest_run
def test_pipelined_requests() -> None:
  'Dispatch requests already buffered in h11 without waiting for another socket readiness event.'
  with running_server() as (server, _), create_connection((server.host, server.port), timeout=1) as socket:
    socket.sendall(b'GET / HTTP/1.1\r\nHost: localhost\r\n\r\n' * 3 +
      b'GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
    received = b''
    while chunk := socket.recv(65536): received += chunk
    utest_val(4, received.count(b'HTTP/1.1 200 '))
    utest_val(4, received.count(b'\r\n\r\nok'))


@utest_run
def test_idle_timeouts() -> None:
  'Expire both speculative and reused connections, releasing capacity for subsequent clients.'
  with running_server(idle_timeout=0.05, max_connections=2) as (server, _):
    for _ in range(4):
      with create_connection((server.host, server.port), timeout=1) as socket:
        utest_val(b'', socket.recv(1))
    conn = HTTPConnection(server.host, server.port, timeout=1)
    try:
      conn.request('GET', '/')
      utest_val(b'ok', conn.getresponse().read())
      assert conn.sock is not None
      utest_val(b'', conn.sock.recv(1))
    finally:
      conn.close()


@utest_run
def test_connection_capacity() -> None:
  'At capacity, a new connection replaces the longest idle connection.'
  with running_server(max_connections=2) as (server, _), ExitStack() as clients:
    conns = []
    for _ in range(3):
      conn = HTTPConnection(server.host, server.port, timeout=1)
      clients.callback(conn.close)
      conn.request('GET', '/')
      utest_val(b'ok', conn.getresponse().read())
      conns.append(conn)
    oldest, middle, newest = conns
    assert oldest.sock is not None
    utest_val(b'', oldest.sock.recv(1))
    for conn in (newest, middle):
      sock = conn.sock
      conn.request('GET', '/')
      utest_val(b'ok', conn.getresponse().read())
      utest_val(sock, conn.sock) # Still the original connection.


@utest_run
def test_connection_capacity_without_idle() -> None:
  'At capacity with every connection active, a new connection is dropped.'
  with running_server(max_connections=1) as (server, _), ExitStack() as clients:
    conn = HTTPConnection(server.host, server.port, timeout=2)
    clients.callback(conn.close)
    conn.request('GET', '/block')
    utest_val(True, App.started.wait(timeout=2), 'blocking request started')
    with create_connection((server.host, server.port), timeout=1) as socket:
      utest_val(b'', socket.recv(1))
    App.unblock.set()
    utest_val(b'ok', conn.getresponse().read())


def read_to_close(socket:Socket) -> bytes:
  'Read until the server closes the connection; a reset counts as a close.'
  received = b''
  try:
    while chunk := socket.recv(65536): received += chunk
  except ConnectionResetError: pass
  return received


def read_response(socket:Socket) -> bytes:
  'Read one complete response with the body "ok".'
  received = b''
  while not received.endswith(b'\r\n\r\nok'):
    chunk = socket.recv(65536)
    if not chunk: break
    received += chunk
  return received


@utest_run
def test_replaced_connection_readable_in_same_batch() -> None:
  '''
  A replaced idle connection that is also readable in the same selector batch must not end the listener loop.
  Event order and worker timing decide which connections are served, so the test only requires that one is.
  '''
  listener:list[Thread] = []
  hold, held, release = Event(), Event(), Event()

  def gated_monotonic() -> float:
    # Stall the listener thread once, so that the next selector batch holds several events.
    if hold.is_set() and listener and current_thread() is listener[0]:
      hold.clear()
      held.set()
      release.wait(timeout=5)
    return monotonic()

  request = b'GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n'
  with patch('pithy.web.server.monotonic', gated_monotonic), running_server(max_connections=1) as (server, thread):
    listener.append(thread)
    with create_connection((server.host, server.port), timeout=2) as idle:
      idle.sendall(b'GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
      utest_val(True, read_response(idle).endswith(b'\r\n\r\nok'), 'first response')
      hold.set()
      server._wake_listener()
      utest_val(True, held.wait(timeout=2), 'listener held')
      idle.sendall(request) # The idle connection becomes readable.
      with create_connection((server.host, server.port), timeout=2) as new: # A new connection arrives at capacity.
        new.sendall(request)
        release.set()
        outcomes = [read_to_close(idle).endswith(b'\r\n\r\nok'), read_to_close(new).endswith(b'\r\n\r\nok')]
      utest_val(True, True in outcomes, f'a connection served: {outcomes}')
    utest_val(True, thread.is_alive(), 'listener alive')
