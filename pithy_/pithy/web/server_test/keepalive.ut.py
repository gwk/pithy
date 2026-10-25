# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Iterator
from contextlib import contextmanager, ExitStack
from http.client import HTTPConnection
from socket import create_connection
from threading import Thread
from unittest.mock import patch

from pithy.web.app import WebApp
from pithy.web.auth import allow_public
from pithy.web.request import Request
from pithy.web.response import Response
from pithy.web.server import ServerConfig, WebServer
from utest import utest_run, utest_val


class App(WebApp):
  @allow_public
  def handle_request(self, request:Request) -> Response:
    return Response(body='ok')


@contextmanager
def running_server(*, timeout:float=10, max_queued:int=64) -> Iterator[tuple[WebServer,Thread]]:
  server = WebServer(app=App(), config=ServerConfig(host='127.0.0.1', num_threads=1,
    conn_timeout=timeout, max_queued=max_queued, log_access=False))
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
  with running_server(timeout=0.05, max_queued=1) as (server, _):
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
  'Idle connections count toward the bounded connection capacity.'
  with running_server(max_queued=1) as (server, _), ExitStack() as clients:
    for _ in range(2):
      conn = HTTPConnection(server.host, server.port, timeout=1)
      clients.callback(conn.close)
      conn.request('GET', '/')
      utest_val(b'ok', conn.getresponse().read())
    with create_connection((server.host, server.port), timeout=1) as socket:
      utest_val(b'', socket.recv(1))
