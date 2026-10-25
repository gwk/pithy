# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Iterator
from contextlib import contextmanager
from errno import EMFILE
from http.client import HTTPConnection
from os import close, dup, listdir
from resource import getrlimit, RLIM_INFINITY, RLIMIT_NOFILE, setrlimit
from socket import create_connection
from threading import Event, Thread
from unittest.mock import patch

from pithy.web.app import WebApp
from pithy.web.auth import allow_public
from pithy.web.request import Request
from pithy.web.response import Response
from pithy.web.server import _resolve_max_connections, ServerConfig, WebServer
from utest import utest, utest_exc, utest_run, utest_val


class App(WebApp):
  @allow_public
  def handle_request(self, request:Request) -> Response:
    return Response(body='ok')


@contextmanager
def running_server() -> Iterator[WebServer]:
  server = WebServer(app=App(), config=ServerConfig(host='127.0.0.1', num_threads=1, log_access=False))
  thread = Thread(target=server.serve_forever)
  thread.start()
  try: yield server
  finally:
    server.shutdown()
    thread.join(timeout=3)
    assert not thread.is_alive()


def get(server:WebServer) -> bytes:
  conn = HTTPConnection(server.host, server.port, timeout=2)
  try:
    conn.request('GET', '/')
    return conn.getresponse().read()
  finally: conn.close()


@utest_run
def test_accept_descriptor_exhaustion() -> None:
  '''
  Descriptor exhaustion pauses accepting instead of ending serve_forever.
  Linux leaves the failed connection in the backlog, while macOS closes it, so only later connections are checked.
  '''
  logged = Event()
  with (patch('pithy.web.server.logI'), patch('pithy.web.server.logE', side_effect=lambda *a, **k: logged.set()) as logE,
   running_server() as server):
    # Confirm that the listener loop is running, and wait for the server to close its socket,
    # so that no descriptor is released after the fillers below take the remaining ones.
    with create_connection((server.host, server.port), timeout=2) as socket:
      socket.sendall(b'GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
      received = b''
      while chunk := socket.recv(65536): received += chunk
    utest_val(True, received.endswith(b'\r\n\r\nok'), 'first response')
    soft, hard = getrlimit(RLIMIT_NOFILE)
    fillers:list[int] = []
    try:
      setrlimit(RLIMIT_NOFILE, (max(int(fd) for fd in listdir('/dev/fd')) + 8, hard))
      try:
        while True: fillers.append(dup(0))
      except OSError as exc:
        utest_val(EMFILE, exc.errno)
      close(fillers.pop()) # Leave exactly one descriptor for the client; the server's accept then fails.
      with create_connection((server.host, server.port), timeout=2):
        utest_val(True, logged.wait(timeout=2), 'accept failure logged')
    finally:
      for fd in fillers: close(fd)
      setrlimit(RLIMIT_NOFILE, (soft, hard))
    utest_val('Accept failed for lack of resources; pausing.', logE.call_args.args[0])
    utest_val(b'ok', get(server))


def resolve(soft:int, hard:int, max_connections:int|None=None, *, raise_fd_limit:bool=False
 ) -> tuple[int,list[tuple[int,int]]]:
  'Resolve the connection cap against a simulated descriptor limit, returning the cap and any limits set.'
  limits_set:list[tuple[int,int]] = []
  with (patch('pithy.web.server.getrlimit', return_value=(soft, hard)),
   patch('pithy.web.server.setrlimit', side_effect=lambda _, limits: limits_set.append(limits))):
    return _resolve_max_connections(max_connections, raise_fd_limit=raise_fd_limit), limits_set


@utest_run
def test_resolve_max_connections() -> None:
  inf = RLIM_INFINITY
  # Default cap: reduced to fit unless raising is enabled.
  utest((1024, []), resolve, 2560, inf)
  utest((1024, []), resolve, inf, inf)
  utest((192, []), resolve, 256, inf)
  utest((1024, [(1088, inf)]), resolve, 256, inf, raise_fd_limit=True)
  utest((448, [(512, 512)]), resolve, 256, 512, raise_fd_limit=True)
  utest_exc(ValueError, resolve, 64, inf)
  # Explicit cap: never reduced.
  utest((100, []), resolve, 256, inf, 100)
  utest_exc(ValueError, resolve, 1024, 524288, 4000)
  utest((4000, [(4064, 524288)]), resolve, 1024, 524288, 4000, raise_fd_limit=True)
  utest_exc(ValueError, resolve, 256, 512, 1000, raise_fd_limit=True)
  utest_exc(ValueError, resolve, 2560, inf, 0)
