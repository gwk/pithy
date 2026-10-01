# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from contextlib import redirect_stdout
from http import HTTPStatus
from io import StringIO
from json import loads
from socket import socket as Socket
from typing import Any, cast
from unittest.mock import patch

from pithy.logs import render_log_json
from pithy.web.app import WebApp
from pithy.web.errors import BadRequestError
from pithy.web.request import Request
from pithy.web.response import Response
from pithy.web.server import ServerConfig, WebServer
from utest import utest_run, utest_val


class TestApp(WebApp):

  def resolve_handler(self, request:Request) -> TestApp:
    if request.path == '/reject': raise BadRequestError('Rejected during routing.')
    return self


  def handle_request(self, request:Request) -> Response:
    request.read_body(1024)
    if request.path == '/raise': raise RuntimeError('Handler failed.')
    if request.path == '/user':
      request.ctx['uid'] = 42
      request.client_addr = ('192.0.2.1', 1234)
    return Response(status=HTTPStatus.OK, body='ok')



class TestSocket:
  'Feed raw HTTP through h11 without opening a network socket.'

  def __init__(self, data:bytes, fail_send:int=0) -> None:
    self.data = data
    self.fail_send = fail_send
    self.sends = 0

  def settimeout(self, timeout:float) -> None: pass
  def shutdown(self, how:int) -> None: pass
  def close(self) -> None: pass

  def recv(self, size:int) -> bytes:
    data, self.data = self.data[:size], self.data[size:]
    return data

  def sendall(self, data:bytes) -> None:
    self.sends += 1
    if self.sends == self.fail_send: raise BrokenPipeError('Client disconnected.')



def access_logs(data:bytes, *, enabled:bool=True, fail_send:int=0) -> list[dict[str,Any]]:
  server = WebServer.__new__(WebServer)
  server.app = TestApp()
  server.config = ServerConfig(log_access=enabled)
  output = StringIO()
  with redirect_stdout(output), patch('pithy.logs.render_log_fn', render_log_json), \
   patch('pithy.web.server.monotonic', side_effect=[10.0, 10.125, 20.0, 20.25]):
    server._handle_connection(cast(Socket, TestSocket(data, fail_send)), ('127.0.0.1', 4321))
  return [record for line in output.getvalue().splitlines() if (record := loads(line)).get('_') == 'access']


def raw_request(target:bytes=b'/', method:bytes=b'GET', version:bytes=b'1.1') -> bytes:
  return method + b' ' + target + b' HTTP/' + version + b'\r\nHost: localhost\r\n\r\n'


@utest_run
def test_keep_alive() -> None:
  'Log once per request; read final application state and reset it between keep-alive cycles.'
  records = access_logs(raw_request(b'/user?q=%FF&x=1') + raw_request(b'/'))
  utest_val([
    dict(level='info', _='access', c='192.0.2.1', u=42, m='GET', p='/user', q='q=%FF&x=1', s=200, d=0.125),
    dict(level='info', _='access', c='127.0.0.1', u=0, m='GET', p='/', q='', s=200, d=0.25),
  ], records)


@utest_run
def test_errors() -> None:
  'Cover routing rejection, handler failure, and rejection before Request construction.'
  for data, status in [
    (raw_request(b'/reject'), 400),
    (raw_request(b'/raise'), 500),
    (raw_request(method=b'CUSTOM'), 501),
    (raw_request(version=b'1.0'), 505),
    (raw_request(b'http://[broken/?x=1'), 400),
  ]:
    records = access_logs(data)
    utest_val(1, len(records))
    utest_val(status, records[0]['s'])
  utest_val('CUSTOM', access_logs(raw_request(method=b'CUSTOM'))[0]['m'])
  record = access_logs(raw_request(b'http://[broken/?x=1'))[0] # Rejected targets are logged verbatim, with an empty query.
  utest_val(('http://[broken/?x=1', ''), (record['p'], record['q']))


@utest_run
def test_send_failure() -> None:
  'Log even when sending fails; retain the sent status when only the body fails.'
  for fail_send, status in [(1, 500), (2, 200)]:
    records = access_logs(raw_request(), fail_send=fail_send)
    utest_val(1, len(records))
    utest_val(status, records[0]['s'])


@utest_run
def test_disabled() -> None:
  utest_val([], access_logs(raw_request(), enabled=False))
