# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Tests for handing off responses to the sender thread, so that a slow download does not occupy a worker.'

from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from http.client import HTTPConnection
from io import BufferedReader
from pathlib import Path
from socket import create_connection, socket as Socket
from tempfile import TemporaryDirectory
from threading import Thread
from time import monotonic, sleep
from typing import Any
from unittest.mock import patch

from pithy.web.app import WebApp
from pithy.web.auth import allow_public
from pithy.web.request import Request
from pithy.web.response import Response
from pithy.web.server import _ResponseSend, max_handed_off_files, ServerConfig, WebServer
from utest import utest, utest_exc, utest_run, utest_val


big_size = 1 << 25 # Far larger than the socket buffers, so that a client that does not read blocks the send.
request_big = b'GET /big HTTP/1.1\r\nHost: localhost\r\n\r\n'


class App(WebApp):

  def __init__(self, file_path:Path|None=None) -> None:
    self.file_path = file_path
    self.files:list[BufferedReader] = []

  @allow_public
  def handle_request(self, request:Request) -> Response:
    if request.path == '/small': return Response(body='small')
    if self.file_path is None: return Response(body=b'x' * big_size)
    file = open(self.file_path, 'rb')
    self.files.append(file)
    return Response(body=file)


@contextmanager
def running_server(app:WebApp, **config:Any) -> Iterator[tuple[WebServer,list[dict[str,Any]]]]:
  'Run a server with one worker, yielding it with the access records that it logs.'
  records:list[dict[str,Any]] = []

  def log_info(_:str, **fields:Any) -> None:
    if _ == 'access': records.append(fields)

  server = WebServer(app=app, config=ServerConfig(host='127.0.0.1', num_threads=1, **config))
  with patch('pithy.web.server.logI', log_info), patch('pithy.web.server.log'):
    thread = Thread(target=server.serve_forever)
    thread.start()
    try: yield server, records
    finally:
      server.shutdown()
      thread.join(10)
  utest(False, thread.is_alive)


def get_small(server:WebServer) -> bytes:
  conn = HTTPConnection(server.host, server.port, timeout=3)
  try:
    conn.request('GET', '/small')
    return conn.getresponse().read()
  finally: conn.close()


def read_response(socket:Socket) -> tuple[bytes,bytes]:
  'Read one response with a content length from a socket.'
  data = b''
  while b'\r\n\r\n' not in data: data += socket.recv(1 << 16)
  head, _, body = data.partition(b'\r\n\r\n')
  length = next(int(line.split(b':')[1]) for line in head.split(b'\r\n') if line.lower().startswith(b'content-length'))
  chunks = [body]
  remaining = length - len(body)
  while remaining > 0:
    chunk = socket.recv(1 << 20)
    assert chunk
    chunks.append(chunk)
    remaining -= len(chunk)
  return head, b''.join(chunks)


def free_slots(server:WebServer) -> int:
  'Count the free connection slots.'
  count = 0
  while server._conn_slots.acquire(blocking=False): count += 1
  return count


@utest_run
def test_slow_download_does_not_occupy_worker() -> None:
  'While a client ignores a large response, the only worker serves other requests. The download then completes intact.'
  with TemporaryDirectory() as tmp:
    path = Path(tmp) / 'big'
    path.write_bytes(b'y' * big_size)
    for app, byte in ((App(), b'x'), (App(path), b'y')):
      with running_server(app, conn_timeout=5.0) as (server, records):
        with create_connection((server.host, server.port), timeout=5) as socket:
          socket.sendall(request_big)
          utest(b'small', get_small, server)
          head, body = read_response(socket)
          utest(True, head.startswith, b'HTTP/1.1 200', _utest_label=repr(head))
          utest(big_size, len, body)
          utest_val(True, set(body[:1024]) == {byte[0]})
          socket.sendall(b'GET /small HTTP/1.1\r\nHost: localhost\r\n\r\n') # The connection is reused.
          utest_val(b'small', read_response(socket)[1])
      if app.files: utest_val(True, app.files[0].closed)
      utest([200, 200, 200], sorted, (r['s'] for r in records))
      utest(True, all, (r['p'] in ('/big', '/small') for r in records))


@utest_run
def test_stalled_client_is_dropped() -> None:
  'Slow client mitigation: a client that stops reading loses its connection, and the access record has the sent status.'
  with running_server(App(), conn_timeout=0.1) as (server, records):
    with create_connection((server.host, server.port), timeout=5) as socket:
      socket.sendall(request_big)
      start = monotonic()
      while not records and monotonic() - start < 3: sleep(0.01)
  utest(1, len, records)
  utest_val(200, records[0]['s'])
  utest_val(0, server._reserved_send_bytes)


@utest_run
def test_slow_client_is_dropped_by_rate() -> None:
  'Slow client mitigation: progress is not enough; the client must also meet the minimum rate.'
  send = object.__new__(_ResponseSend)
  send.started = send.last_progress = 100.0
  send.timeout = 10.0
  send.min_rate = 1000.0
  send.sent = 5000
  utest_val(110.0, send.deadline) # Stall limit.
  send.last_progress = 200.0
  utest_val(115.0, send.deadline) # Rate limit.


@utest_run
def test_capacity_limits() -> None:
  'A response beyond the memory or file limits stays with its worker.'
  server = WebServer(app=WebApp(), config=ServerConfig(host='127.0.0.1', send_buffer_limit=1000))
  try:
    def make(size:int, *, file:bool=False) -> _ResponseSend:
      send = object.__new__(_ResponseSend)
      send.buffers = deque()
      send.body = b'x' * size
      send.file = send.file_to_close = object() if file else None # type: ignore[assignment]
      send.chunk_size = 1
      send.charge = 0
      return send

    utest(True, server._reserve_send, make(600))
    utest(False, server._reserve_send, make(600))
    utest_val(600, server._reserved_send_bytes)
    server._reserved_send_bytes = 0
    server._reserved_send_files = max_handed_off_files
    utest(True, server._reserve_send, make(1))
    utest(False, server._reserve_send, make(1, file=True))
  finally: server.shutdown()


@utest_run
def test_response_over_limit_is_sent_by_worker() -> None:
  with running_server(App(), send_buffer_limit=0, conn_timeout=5.0) as (server, _):
    with create_connection((server.host, server.port), timeout=5) as socket:
      socket.sendall(request_big)
      utest(big_size, len, read_response(socket)[1])


@utest_run
def test_shutdown_abandons_slow_downloads() -> None:
  'Shutdown waits for a held response for only `conn_timeout`, and then closes the connection.'
  with TemporaryDirectory() as tmp:
    path = Path(tmp) / 'big'
    path.write_bytes(b'y' * big_size)
    app = App(path)
    start = monotonic()
    with running_server(app, conn_timeout=0.2, min_send_rate=1e9) as (server, _):
      with create_connection((server.host, server.port), timeout=5) as socket:
        socket.sendall(request_big)
        utest(b'small', get_small, server)
        server.shutdown()
    utest_val(True, monotonic() - start < 3)
    utest_val(True, app.files[0].closed)
    utest(server.max_connections, free_slots, server)


@utest_run
def test_send_config_validation() -> None:
  for value in (0, -1, float('inf'), float('nan')):
    utest_exc(ValueError, lambda: ServerConfig(min_send_rate=value))
  utest_exc(ValueError, lambda: ServerConfig(send_buffer_limit=-1))
