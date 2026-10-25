# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from contextlib import redirect_stdout
from http import HTTPStatus
from io import StringIO
from json import loads
from typing import Any, cast
from unittest.mock import patch

from h11 import Connection, Data, LocalProtocolError
from pithy.logs import render_log_json
from pithy.web.app import WebApp
from pithy.web.auth import allow_public
from pithy.web.destination import Destination
from pithy.web.errors import BadRequestError
from pithy.web.request import Request
from pithy.web.requestconn import ClientProtocolError
from pithy.web.response import Response
from pithy.web.server_test.testsocket import handle_connection, TestSocket
from utest import utest_run, utest_val


class TestApp(WebApp):

  def resolve_destination(self, request:Request) -> Destination:
    if request.path == '/reject': raise BadRequestError('Rejected during routing.')
    return super().resolve_destination(request)


  @allow_public
  def handle_request(self, request:Request) -> Response:
    request.read_body(1024)
    if request.path == '/raise': raise RuntimeError('Handler failed.')
    if request.path == '/user':
      request.ctx['uid'] = 42
      request.client_addr = ('192.0.2.1', 1234)
    return Response(status=HTTPStatus.OK, body='ok')



def access_logs(data:bytes, *, enabled:bool=True, fail_send:int=0) -> list[dict[str,Any]]:
  output = StringIO()
  with redirect_stdout(output), patch('pithy.logs.render_log_fn', render_log_json), \
   patch('pithy.web.server.monotonic', side_effect=[10.0, 10.125, 20.0, 20.25]):
    handle_connection(TestApp(), TestSocket(data, fail_send=fail_send), log_access=enabled)
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
  'Log even when sending fails: 0 when the headers were not sent, the sent status when only the body fails.'
  for fail_send, status in [(1, 0), (2, 200)]:
    records = access_logs(raw_request(), fail_send=fail_send)
    utest_val(1, len(records))
    utest_val(status, records[0]['s'])


@utest_run
def test_disabled() -> None:
  utest_val([], access_logs(raw_request(), enabled=False))


malformed_body = b'POST / HTTP/1.1\r\nHost: localhost\r\nTransfer-Encoding: chunked\r\n\r\nzz\r\n'
incomplete_body = b'POST / HTTP/1.1\r\nHost: localhost\r\nContent-Length: 100\r\n\r\nbody'


def connection_logs(data:bytes, *, enabled:bool, timeout:bool=False, reset:bool=False, app:WebApp|None=None
 ) -> tuple[list[dict[str,Any]],bytes]:
  socket = TestSocket(data, timeout=timeout, reset=reset)
  output = StringIO()
  with redirect_stdout(output), patch('pithy.logs.render_log_fn', render_log_json):
    handle_connection(app or TestApp(), socket, log_access=enabled)
  return [loads(line) for line in output.getvalue().splitlines()], bytes(socket.sent)


@utest_run
def test_protocol_failures() -> None:
  'Log malformed requests and bodies as protocol_failure records, without request bytes in logs or responses.'
  secret = b'SECRET_SENTINEL'
  chunked = b'POST / HTTP/1.1\r\nHost: localhost\r\nTransfer-Encoding: chunked\r\n\r\n'
  for enabled in (False, True):
    for data, stage, sent in [
      (b'GET /?token=' + secret + b' BAD\r\n\r\n', 'request_headers', False),
      (b'GET / HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer ' + secret + b'\x00\r\n\r\n',
        'request_headers', False),
      (chunked + secret + b'\r\n', 'request_body', False),
      (chunked + b'1\r\nx' + secret + b'\r\n', 'request_body', False),
      (chunked.replace(b' / ', b' /reject ') + secret + b'\r\n', 'drain_body', True),
    ]:
      records, response = connection_logs(data, enabled=enabled)
      utest_val(False, secret.decode() in repr(records))
      utest_val(False, secret in response)
      utest_val(True, response.startswith(b'HTTP/1.1 400 '), response) # Malformed headers are answered too, with a bare 400.
      failures = [r for r in records if r['_'] == 'protocol_failure']
      utest_val(1, len(failures))
      record = failures[0]
      utest_val(400, record['status'])
      utest_val(stage, record['stage'])
      utest_val('info' if sent else 'error', record['level'])
      utest_val(sent, record['response_sent'])
      utest_val(400 if sent else None, record['response_status'])
      utest_val(len(data), record['received_bytes'])
      utest_val(['127.0.0.1', 4321], record['client_addr'])
      utest_val(True, record['elapsed'] >= 0)
      utest_val(False, 'exc' in record or 'error' in record or 'exception_type' in record)
    records, response = connection_logs(raw_request(b'http://[broken/?token=' + secret), enabled=enabled)
    utest_val(False, secret.decode() in repr([r for r in records if r['_'] != 'access'])) # The access log records targets.
    utest_val(False, secret in response)
    utest_val(True, b'Invalid request target.' in response)


@utest_run
def test_incomplete_timeout() -> None:
  'Log a timeout during partial request headers; an idle keep-alive timeout is not a failure.'
  for enabled in (False, True):
    for prefix in (b'', raw_request(b'/user')):
      for partial in (b'', b'GET /?token=SECRET_SENTINEL HTTP/1.1\r\nHost:'):
        data = prefix + partial
        records, response = connection_logs(data, enabled=enabled, timeout=True)
        utest_val(False, 'SECRET_SENTINEL' in repr(records))
        utest_val(bool(partial), response.endswith(b'Request Timeout'), response) # A bare 408; an idle timeout gets nothing.
        failures = [r for r in records if r['_'] == 'protocol_failure']
        utest_val(1 if partial else 0, len(failures))
        if partial:
          record = failures[0]
          utest_val(408, record['status'])
          utest_val('request_headers', record['stage'])
          utest_val(False, record['response_sent'])
          utest_val(None, record['response_status'])
          utest_val('', record['method'])
          utest_val(len(data), record['received_bytes'])


class ChainedApp(TestApp):

  @allow_public
  def handle_request(self, request:Request) -> Response:
    try: request.read_body(1024)
    except Exception as exc: raise RuntimeError('Wrapped body failure.') from exc
    return Response(body='ok')


@utest_run
def test_chained_protocol_failure() -> None:
  'Log a protocol error wrapped by the application as an application exception; the rendered cause holds no request bytes.'
  data = b'POST / HTTP/1.1\r\nHost: localhost\r\nTransfer-Encoding: chunked\r\n\r\nSECRET_SENTINEL\r\n'
  for enabled in (False, True):
    records, response = connection_logs(data, enabled=enabled, app=ChainedApp())
    utest_val(False, 'SECRET_SENTINEL' in repr(records))
    utest_val(False, b'SECRET_SENTINEL' in response)
    utest_val(True, response.startswith(b'HTTP/1.1 500 '), response)
    utest_val(1, len([r for r in records if r['_'] == 'protocol_failure']))
    errors = [r for r in records if r['_'] == 'Unhandled application exception.']
    utest_val([True], [('Wrapped body failure.' in str(r['exc']) and '400 Bad Request.' in str(r['exc'])) for r in errors])


class CatchApp(TestApp):

  @allow_public
  def handle_request(self, request:Request) -> Response:
    try: request.read_body(1024)
    except ClientProtocolError as exc: return Response(HTTPStatus.BAD_REQUEST, body=f'{exc.status.value}: {exc}')
    return Response(body='ok')


@utest_run
def test_client_protocol_error_contract() -> None:
  'Raise ClientProtocolError from body reads with a fixed message and the status that the server would have sent.'
  for data, timeout, expected in [
   (malformed_body, False, b'400: 400 Bad Request.'), (incomplete_body, True, b'408: 408 Request Timeout.')]:
    records, response = connection_logs(data, enabled=False, timeout=timeout, app=CatchApp())
    utest_val(True, response.startswith(b'HTTP/1.1 400 '), response)
    utest_val(True, response.endswith(expected), response)
    utest_val([400 if timeout is False else 408], [r['status'] for r in records if r['_'] == 'protocol_failure'])


class ContextApp(TestApp):

  @allow_public
  def handle_request(self, request:Request) -> Response:
    try: request.read_body(1024)
    except Exception: raise RuntimeError('Bug in the failure handler.')
    return Response(body='ok')


@utest_run
def test_context_protocol_failure() -> None:
  'Log a server bug raised while handling a protocol failure with its traceback; implicit context must not mask it.'
  data = b'POST / HTTP/1.1\r\nHost: localhost\r\nTransfer-Encoding: chunked\r\n\r\nzz\r\n'
  records, response = connection_logs(data, enabled=False, app=ContextApp())
  utest_val(True, response.startswith(b'HTTP/1.1 500 '), response)
  utest_val(1, len([r for r in records if r['_'] == 'protocol_failure']))
  errors = [r for r in records if r['_'] == 'Unhandled application exception.']
  utest_val([('error', 'POST', '/', True)],
    [(r['level'], r['method'], r['path'], 'Bug in the failure handler.' in str(r['exc'])) for r in errors])


@utest_run
def test_close_error_level() -> None:
  'Log a socket error while draining an unread body at info level: the response was sent and the client left early.'
  data = b'POST /reject HTTP/1.1\r\nHost: localhost\r\nContent-Length: 100\r\n\r\nbody'
  records, response = connection_logs(data, enabled=False, reset=True)
  utest_val(True, response.startswith(b'HTTP/1.1 400 '), response)
  utest_val([('Connection close error.', 'info', True)], [(r['_'], r['level'], 'ConnectionResetError' in str(r['exc']))
    for r in records])


@utest_run
def test_body_timeout_and_eof() -> None:
  'Log body timeouts and premature EOF in the stage where they occur, whether reading or draining.'
  for enabled in (False, True):
    for path, stage, status in [(b'/', 'request_body', None), (b'/reject', 'drain_body', 400)]:
      data = b'POST ' + path + b' HTTP/1.1\r\nHost: localhost\r\nContent-Length: 100\r\n\r\nSECRET_SENTINEL'
      for timeout in (False, True):
        records, response = connection_logs(data, enabled=enabled, timeout=timeout)
        utest_val(False, 'SECRET_SENTINEL' in repr(records))
        utest_val(False, b'SECRET_SENTINEL' in response)
        failures = [r for r in records if r['_'] == 'protocol_failure']
        utest_val(1, len(failures))
        utest_val(408 if timeout else 400, failures[0]['status'])
        utest_val(stage, failures[0]['stage'])
        utest_val(status, failures[0]['response_status'])
        utest_val('error' if status is None else 'info', failures[0]['level'])


@utest_run
def test_local_protocol_error() -> None:
  'Log a local protocol error during response sending as an ordinary exception with its traceback, since it is a server bug.'
  original_send = Connection.send

  def send(conn:Connection, event:Any) -> bytes|None:
    if isinstance(event, Data): raise LocalProtocolError('Invalid body.')
    return cast(bytes|None, original_send(conn, event))

  for enabled in (False, True):
    with patch.object(Connection, 'send', send):
      records, response = connection_logs(raw_request(), enabled=enabled)
    utest_val(True, response.startswith(b'HTTP/1.1 200 '), response)
    utest_val([], [r for r in records if r['_'] == 'protocol_failure'])
    errors = [r for r in records if r['_'] == 'Connection handling error.']
    utest_val(1, len(errors))
    exc_text = str(errors[0]['exc'])
    utest_val((True, True), ('LocalProtocolError' in exc_text, 'Invalid body.' in exc_text))


class SwallowApp(TestApp):

  @allow_public
  def handle_request(self, request:Request) -> Response:
    try: request.read_body(1024)
    except Exception: pass
    return Response(body='ok')


@utest_run
def test_body_failure_responses() -> None:
  'Answer a malformed body with a bare 400 and a body timeout with a bare 408; a client that closed its end gets no response.'
  for data, timeout, status in [(malformed_body, False, 400), (incomplete_body, True, 408), (incomplete_body, False, None)]:
    records, response = connection_logs(data, enabled=True, timeout=timeout)
    if status is None: utest_val(b'', response)
    else: utest_val(True, response.startswith(f'HTTP/1.1 {status} '.encode()), response)
    utest_val([status or 0], [r['s'] for r in records if r['_'] == 'access'])


@utest_run
def test_swallowed_body_failure() -> None:
  'Log a body read failure in the stage where it is detected, even when the handler swallows it and responds normally.'
  for data, timeout, status in [(malformed_body, False, 400), (incomplete_body, True, 408)]:
    records, response = connection_logs(data, enabled=False, timeout=timeout, app=SwallowApp())
    utest_val(True, response.startswith(b'HTTP/1.1 200 '), response)
    failures = [(r['status'], r['stage'], r['response_status']) for r in records if r['_'] == 'protocol_failure']
    utest_val([(status, 'request_body', None)], failures)


@utest_run
def test_application_exception_context() -> None:
  'Log application exceptions with their traceback, method and path.'
  records, _ = connection_logs(raw_request(b'/raise?x=1'), enabled=False)
  utest_val([('GET', '/raise', True)], [(r['method'], r['path'], 'RuntimeError' in str(r['exc']))
    for r in records if r['_'] == 'Unhandled application exception.'])


@utest_run
def test_expect_continue_rejection() -> None:
  'Log at info level when a client rejected before sending its body closes the connection, as it should.'
  data = b'POST /reject HTTP/1.1\r\nHost: localhost\r\nContent-Length: 100\r\nExpect: 100-continue\r\n\r\n'
  records, response = connection_logs(data, enabled=False)
  utest_val(True, response.startswith(b'HTTP/1.1 400 '), response)
  utest_val([('protocol_failure', 'info', 'drain_body', 400)], [(r['_'], r['level'], r.get('stage'), r.get('response_status'))
    for r in records])
