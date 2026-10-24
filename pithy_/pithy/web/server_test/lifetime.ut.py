# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from contextlib import redirect_stdout
from gc import disable, enable, isenabled
from http import HTTPStatus
from io import StringIO
from typing import Any
from unittest.mock import patch
from weakref import ref, ReferenceType

from pithy.logs import render_log_fn
from pithy.web.app import WebApp
from pithy.web.auth import allow_public
from pithy.web.request import Request
from pithy.web.requestconn import RequestConn
from pithy.web.response import Response
from pithy.web.server_test.testsocket import handle_connection, TestSocket
from utest import utest_run, utest_val


class LifetimeApp(WebApp):

  def __init__(self, read_body:bool=False, catch_read_error:bool=False) -> None:
    self.read_body = read_body
    self.catch_read_error = catch_read_error
    self.reading_body = False
    self.requests:list[ReferenceType[Request]] = []
    self.readers:list[RequestConn] = []


  def check_released(self, when:str) -> None:
    for previous in self.requests: utest_val(None, previous(), f'previous request at {when}')


  @allow_public
  def handle_request(self, request:Request) -> Response:
    self.check_released('dispatch')
    self.requests.append(ref(request))
    assert request.conn is not None
    self.readers.append(request.conn) # Retaining a body reader must not keep its request alive.
    if self.read_body:
      self.reading_body = True
      try: request.read_body(max_bytes=64)
      except Exception:
        if not self.catch_read_error: raise
        return Response(HTTPStatus.BAD_REQUEST, body='Body read failed.')
      finally: self.reading_body = False
    return Response(body='ok')



class LifetimeSocket(TestSocket):
  'Check that every completed request has been released before each socket read outside of body reads, and before closing.'

  def __init__(self, app:LifetimeApp, *chunks:bytes, fail_send:int=0, timeout:bool=False) -> None:
    super().__init__(*chunks, fail_send=fail_send, timeout=timeout)
    self.app = app
    self.closes = 0

  def recv(self, size:int) -> bytes:
    if not self.app.reading_body: self.app.check_released('recv') # The current request is alive while its handler reads.
    return super().recv(size)

  def close(self) -> None:
    self.app.check_released('close')
    self.closes += 1


@utest_run
def test_request_lifetime() -> None:
  'Release completed requests before another socket read, pipelined dispatch or connection closure.'
  keep_alive = b'GET / HTTP/1.1\r\nHost: localhost\r\n\r\n'
  close = b'GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n'
  unread_body = b'POST / HTTP/1.1\r\nHost: localhost\r\nContent-Length: 4\r\n\r\n'
  for enabled in (False, True):
    for chunks, count in [([close], 1), ([keep_alive, close], 2), ([keep_alive + close], 2), ([unread_body, b'body'], 1)]:
      app = LifetimeApp()
      socket = LifetimeSocket(app, *chunks)
      with redirect_stdout(StringIO()):
        handle_connection(app, socket, log_access=enabled)
      utest_val(count, len(app.requests))
      utest_val(1, socket.closes)


@utest_run
def test_request_lifetime_access_log_failure() -> None:
  'Release the request before connection closure when access logging raises.'
  app = LifetimeApp()

  def render_log(level:str, _:str, **kwargs:Any) -> str:
    if _ == 'access': raise RuntimeError('Access logging failed.')
    return render_log_fn(level, _, **kwargs)

  socket = LifetimeSocket(app, b'GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
  with redirect_stdout(StringIO()), patch('pithy.logs.render_log_fn', render_log):
    handle_connection(app, socket, log_access=True)
  utest_val(1, len(app.requests))
  utest_val(1, socket.closes)


@utest_run
def test_request_lifetime_failed_body_read() -> None:
  'Release the request before connection closure when reading the body fails, whether or not the handler catches the error.'
  malformed = b'POST / HTTP/1.1\r\nHost: localhost\r\nTransfer-Encoding: chunked\r\n\r\nzz\r\n'
  incomplete = b'POST / HTTP/1.1\r\nHost: localhost\r\nContent-Length: 4\r\n\r\nbo'
  for data, timeout in [(malformed, False), (incomplete, False), (incomplete, True)]:
    for catch_read_error in (False, True):
      for fail_send in (0, 1):
        app = LifetimeApp(read_body=True, catch_read_error=catch_read_error)
        socket = LifetimeSocket(app, data, fail_send=fail_send, timeout=timeout)
        gc_was_enabled = isenabled()
        disable() # Release must not depend on the cycle collector.
        try:
          with redirect_stdout(StringIO()):
            handle_connection(app, socket, log_access=True)
        finally:
          if gc_was_enabled: enable()
        utest_val(1, len(app.requests))
        utest_val(1, socket.closes)
