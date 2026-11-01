# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Tests for slow client mitigation. A client that sends too slowly loses its connection.
Slow handlers and clients that meet the minimum rate are not affected.

Most tests script a socket against a fake clock, using the default limits, so that they do not sleep.
'''

from socket import create_connection
from threading import Thread
from time import sleep
from unittest.mock import patch

from pithy.web.app import WebApp
from pithy.web.auth import allow_public
from pithy.web.request import Request
from pithy.web.response import Response
from pithy.web.server import ServerConfig, WebServer
from pithy.web.server_test.testsocket import handle_connection, TestSocket
from utest import utest_exc, utest_run, utest_val


post_head = b'POST / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\nContent-Length: %d\r\n\r\n'


class ClockSocket(TestSocket):
  'A scripted socket where each read advances a fake clock by `delay` seconds, or times out if the delay is too long.'

  def __init__(self, *chunks:bytes, delay:float) -> None:
    super().__init__(*chunks)
    self.delay = delay
    self.now = 0.0
    self.limit = 0.0
    self.reads = 0

  def settimeout(self, timeout:float) -> None:
    self.limit = timeout

  def recv(self, size:int) -> bytes:
    self.reads += 1
    if self.delay > self.limit:
      self.now += self.limit
      raise TimeoutError('Timed out.')
    self.now += self.delay
    return super().recv(size)


class App(WebApp):

  def __init__(self, socket:ClockSocket|None=None, *, read_body:bool=True, handler_time:float=0.0) -> None:
    self.socket = socket
    self.read_body = read_body
    self.handler_time = handler_time

  @allow_public
  def handle_request(self, request:Request) -> Response:
    if self.socket: self.socket.now += self.handler_time
    if not self.read_body: return Response(body='rejected')
    return Response(body=f'read {len(request.read_body(1 << 20))}')


def run_scripted(socket:ClockSocket, app:App) -> None:
  'Handle one connection with the default limits, reading time from the clock of `socket`.'
  with patch('pithy.web.server.monotonic', lambda: socket.now), patch('pithy.web.server.logI'), patch('pithy.web.server.log'):
    handle_connection(app, socket, log_access=False)


def one_byte_chunks(data:bytes) -> list[bytes]:
  return [bytes((byte,)) for byte in data]


@utest_run
def test_min_read_rate_validation() -> None:
  for value in (0, -1, float('inf'), float('nan')):
    utest_exc(ValueError, lambda: ServerConfig(min_read_rate=value))


@utest_run
def test_trickled_headers_time_out() -> None:
  'Each read finishes well within the per-read timeout, but the total read time is still limited.'
  data = b'GET / HTTP/1.1\r\nHost: localhost\r\nX-Long: ' + b'a' * 1000
  socket = ClockSocket(*one_byte_chunks(data), delay=1.0)
  run_scripted(socket, App())
  utest_val(True, socket.sent.startswith(b'HTTP/1.1 408'), socket.sent)
  utest_val(True, socket.now <= 10.1, socket.now) # The initial budget plus the little that the received bytes earned.


@utest_run
def test_trickled_body_times_out() -> None:
  socket = ClockSocket(post_head % 1000, *one_byte_chunks(b'a' * 1000), delay=1.0)
  run_scripted(socket, App())
  utest_val(True, socket.sent.startswith(b'HTTP/1.1 408'), socket.sent)
  utest_val(True, socket.now <= 10.1, socket.now)


@utest_run
def test_trickled_drain_is_limited_in_total() -> None:
  'Each read finishes within `drain_timeout`, but the whole drain stops once `drain_timeout` is used up.'
  socket = ClockSocket(post_head % 1000, *one_byte_chunks(b'a' * 1000), delay=0.1)
  run_scripted(socket, App(read_body=False))
  utest_val(True, b'rejected' in socket.sent, socket.sent)
  utest_val(True, socket.reads <= 12, socket.reads) # One read for the head, then one second of drain reads.


@utest_run
def test_adequate_rate_outlasts_initial_budget() -> None:
  'A long upload succeeds when the client meets the minimum rate.'
  socket = ClockSocket(post_head % 40000, *[b'a' * 1000] * 40, delay=0.5)
  run_scripted(socket, App())
  utest_val(True, socket.now > ServerConfig().conn_timeout, socket.now)
  utest_val(True, socket.sent.endswith(b'read 40000'), socket.sent)


@utest_run
def test_slow_handler_is_not_charged() -> None:
  'Time that a handler spends before reading the body does not count against the read budget.'
  socket = ClockSocket(post_head % 2, b'ok', delay=0.01)
  run_scripted(socket, App(socket, handler_time=1000.0))
  utest_val(True, socket.sent.endswith(b'read 2'), socket.sent)


@utest_run
def test_real_socket_timeout() -> None:
  'End to end check that a read budget ends a trickling connection on a real socket.'
  server = WebServer(app=App(), config=ServerConfig(host='127.0.0.1', num_threads=1, log_access=False, conn_timeout=0.05,
    min_read_rate=1000.0))
  with patch('pithy.web.server.logI'), patch('pithy.web.server.log'):
    thread = Thread(target=server.serve_forever)
    thread.start()
    try:
      with create_connection((server.host, server.port), timeout=5) as socket:
        socket.sendall(b'GET / HTTP/1.1\r\nHost: localhost\r\nX-Long: ')
        received = b''
        try:
          for byte in b'a' * 100: # Each gap is shorter than the timeout, and the budget runs out in 50 ms.
            socket.sendall(bytes((byte,)))
            sleep(0.005)
        except OSError: pass
        try:
          while chunk := socket.recv(4096): received += chunk
        except ConnectionResetError: pass
    finally:
      server.shutdown()
      thread.join(5)
  utest_val(False, thread.is_alive())
  utest_val(True, received.startswith(b'HTTP/1.1 408'), received)
