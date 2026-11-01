# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Iterator response framing, stream admission, SSE cancellation and ownership across threads.'

from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from http.client import HTTPConnection, IncompleteRead
from json import loads
from socket import create_connection, SHUT_RDWR
from subprocess import run
from sys import executable
from threading import current_thread, Event, Thread
from time import monotonic, sleep
from typing import Any
from unittest.mock import patch
from weakref import ref

from pithy.web.app import WebApp
from pithy.web.auth import allow_public
from pithy.web.request import Request
from pithy.web.response import Response
from pithy.web.server import deadline_scan_interval, ServerConfig, WebServer
from pithy.web.server_test.testsocket import handle_connection, TestSocket
from pithy.web.sse import SseChannel, SseEvent, SseResponse
from utest import utest_exc, utest_run, utest_val


class Body(Iterator[bytes]):

  def __init__(self, *, fail:bool=False, invalid:bool=False) -> None:
    self.chunks = iter([b'first', b'', b'second'])
    self.closed = Event()
    self.close_count = 0
    self.thread = ''
    self.fail = fail
    self.invalid = invalid


  def __next__(self) -> bytes:
    self.thread = current_thread().name
    if self.fail: raise ValueError('Iterator failed.')
    if self.invalid: return 'invalid' # type: ignore[return-value]
    return next(self.chunks)


  def close(self) -> None:
    self.close_count += 1
    self.closed.set()


class App(WebApp):

  def __init__(self) -> None:
    self.channels:list[SseChannel] = []
    self.bodies:list[Body] = []
    self.last_event_id = ''


  @allow_public
  def handle_request(self, request:Request) -> Response:
    if request.path == '/small': return Response(body='small')
    if request.path in ('/finite', '/fail', '/invalid', '/large'):
      body = Body(fail=request.path == '/fail', invalid=request.path == '/invalid')
      if request.path == '/large': body.chunks = iter([b'x' * (1 << 24)])
      self.bodies.append(body)
      return Response(body=body)
    channel = SseChannel()
    channel.send(SseEvent(data='ready', id='1'))
    self.channels.append(channel)
    self.last_event_id = request.headers.get('last-event-id', '')
    return SseResponse(channel, heartbeat_interval=0.02)


  def finish_response(self, request:Request, response:Response) -> Response:
    if request.path == '/replace': return Response(body='replaced')
    return response


@contextmanager
def running_server(app:App, **config:Any) -> Iterator[tuple[WebServer,list[dict[str,Any]]]]:
  records:list[dict[str,Any]] = []
  errors:list[BaseException] = []

  def log_info(message:str, **fields:Any) -> None:
    if message == 'access': records.append(fields)

  server = WebServer(app=app, config=ServerConfig(host='127.0.0.1', num_threads=1, **config))

  def serve() -> None:
    try: server.serve_forever()
    except BaseException as exc: errors.append(exc)

  with patch('pithy.web.server.logI', log_info):
    thread = Thread(target=serve)
    thread.start()
    try: yield server, records
    finally:
      server.shutdown()
      thread.join(3)
  utest_val(False, thread.is_alive())
  utest_val([], errors)
  utest_val({}, server._active_workers)
  utest_val(True, all(not worker.is_alive() for worker in server._stream_workers))


def get(server:WebServer, path:str, *, method:str='GET') -> tuple[int,bytes]:
  with closing(HTTPConnection(server.host, server.port, timeout=2)) as client:
    client.request(method, path)
    response = client.getresponse()
    return response.status, response.read()


@utest_run
def test_finite_stream_chunking_keep_alive_and_access() -> None:
  app = App()
  with running_server(app, max_streams=1) as (server, records):
    with closing(HTTPConnection(server.host, server.port, timeout=2)) as client:
      client.request('GET', '/finite')
      response = client.getresponse()
      utest_val('chunked', response.getheader('transfer-encoding'))
      utest_val(None, response.getheader('content-length'))
      utest_val(b'firstsecond', response.read())
      original_socket = client.sock
      client.request('GET', '/small')
      utest_val(b'small', client.getresponse().read())
      utest_val(original_socket, client.sock)
    utest_val(True, app.bodies[0].closed.wait(1))
    utest_val(1, app.bodies[0].close_count)
    utest_val(True, '-stream-' in app.bodies[0].thread)
  utest_val(['/finite', '/small'], sorted(record['p'] for record in records))
  utest_val([200, 200], [record['s'] for record in records])


@utest_run
def test_sse_admission_preserves_normal_workers() -> None:
  app = App()
  with running_server(app, max_streams=1, worker_warn_after=0.02) as (server, records), \
   patch('pithy.web.server.logW') as warning:
    with closing(HTTPConnection(server.host, server.port, timeout=2)) as client:
      client.request('GET', '/events', headers={'Last-Event-ID': 'previous'})
      response = client.getresponse()
      utest_val('text/event-stream;charset=utf-8', response.getheader('content-type'))
      utest_val(b'id: 1\ndata: ready\n\n', response.read(19))
      utest_val('previous', app.last_event_id)
      utest_val((503, b'Service Unavailable'), get(server, '/events'))
      utest_val(True, app.channels[1].closed.wait(1))
      utest_val((200, b'small'), get(server, '/small'))
      utest_val(b': heartbeat\n\n', response.read(13))
      app.channels[0].finish()
      utest_val(b'', response.read())
      utest_val(True, app.channels[0].closed.wait(1))
      # The released stream slot admits another stream.
      client.request('GET', '/events')
      response = client.getresponse()
      utest_val(200, response.status)
      app.channels[2].finish()
      response.read()
    # Ordinary workers can exceed the short threshold on a loaded machine; only stream workers are under test.
    utest_val([], [call for call in warning.call_args_list if '-stream-' in call.kwargs.get('worker', '')])
  utest_val(4, len(records))
  utest_val([200, 200, 200, 503], sorted(record['s'] for record in records))


@utest_run
def test_head_replacement_and_disabled_streams_close_without_iteration() -> None:
  app = App()
  with running_server(app, max_streams=0) as (server, _):
    utest_val((200, b''), get(server, '/events', method='HEAD'))
    utest_val(True, app.channels[0].closed.wait(1))
    utest_val((200, b'replaced'), get(server, '/replace'))
    utest_val(True, app.channels[1].closed.wait(1))
    utest_val((503, b'Service Unavailable'), get(server, '/finite'))
    utest_val(True, app.bodies[0].closed.wait(1))
    utest_val('', app.bodies[0].thread)
    utest_val([], server._stream_workers)


@utest_run
def test_lifetime_and_shutdown_close_quiet_channels() -> None:
  for shutting_down in (False, True):
    app = App()
    start = monotonic()
    with running_server(app, stream_max_duration=0.15 if not shutting_down else 300) as (server, records):
      with closing(HTTPConnection(server.host, server.port, timeout=2)) as client:
        client.request('GET', '/events')
        response = client.getresponse()
        if shutting_down: server.shutdown()
        response.read()
        utest_val(True, app.channels[0].closed.wait(1))
    utest_val(True, monotonic() - start < 2)
    utest_val([200], [record['s'] for record in records])


class GeneratorApp(App):

  def __init__(self, generate:Callable[[],Iterator[bytes]]) -> None:
    super().__init__()
    self.generate = generate


  @allow_public
  def handle_request(self, request:Request) -> Response:
    return Response(body=self.generate())


def endless_chunks() -> Iterator[bytes]:
  while True:
    yield b'chunk'
    sleep(0.01)


@utest_run
def test_lifetime_and_shutdown_abort_plain_iterator() -> None:
  for shutting_down in (False, True):
    app = GeneratorApp(endless_chunks)
    with running_server(app, stream_max_duration=0.1 if not shutting_down else 300) as (server, _):
      with closing(HTTPConnection(server.host, server.port, timeout=2)) as client:
        client.request('GET', '/')
        response = client.getresponse()
        if shutting_down: server.shutdown()
        utest_exc(IncompleteRead, response.read)


@utest_run
def test_iterator_finishing_after_lifetime_is_complete() -> None:
  def late_finish() -> Iterator[bytes]:
    yield b'all'
    sleep(0.15)

  app = GeneratorApp(late_finish)
  with running_server(app, stream_max_duration=0.1) as (server, _):
    utest_val((200, b'all'), get(server, '/'))


@utest_run
def test_terminal_chunk_of_complete_stream_uses_ordinary_timeout() -> None:
  timeouts:list[float] = []

  class RecordingSocket(TestSocket):
    def settimeout(self, timeout:float) -> None: timeouts.append(timeout)

  handle_connection(App(), RecordingSocket(b'GET /finite HTTP/1.1\r\nHost: localhost\r\n\r\n'), log_access=False)
  utest_val(True, len(timeouts) >= 4)
  utest_val(True, min(timeouts) > deadline_scan_interval)


@utest_run
def test_disconnect_closes_source_and_releases_capacity() -> None:
  app = App()
  with running_server(app, max_streams=1) as (server, _):
    with create_connection((server.host, server.port), timeout=2) as socket:
      socket.sendall(b'GET /events HTTP/1.1\r\nHost: localhost\r\n\r\n')
      assert socket.recv(4096)
      socket.shutdown(SHUT_RDWR)
    utest_val(True, app.channels[0].closed.wait(2))
    utest_val((200, b'firstsecond'), get(server, '/finite'))


@utest_run
def test_iterator_failures_close_connection_without_second_response() -> None:
  for path in ('/fail', '/invalid'):
    app = App()
    with running_server(app, max_streams=1) as (server, records), patch('pithy.web.server.logE') as error:
      with closing(HTTPConnection(server.host, server.port, timeout=2)) as client:
        client.request('GET', path)
        response = client.getresponse()
        utest_val(200, response.status)
        utest_exc(IncompleteRead, response.read)
      utest_val(True, app.bodies[0].closed.wait(1))
      utest_val(1, app.bodies[0].close_count)
      utest_val((200, b'small'), get(server, '/small'))
      error.assert_called_once()
    utest_val([200, 200], [record['s'] for record in records])


@utest_run
def test_header_and_chunk_send_failures_close_source() -> None:
  for fail_send in (1, 2, 3):
    app = App()
    socket = TestSocket(b'GET /finite HTTP/1.1\r\nHost: localhost\r\n\r\n', fail_send=fail_send)
    with patch('pithy.web.server.logI'):
      handle_connection(app, socket, log_access=True)
    utest_val(True, app.bodies[0].closed.is_set())
    utest_val(1, app.bodies[0].close_count)


@utest_run
def test_stream_config_validation() -> None:
  utest_exc(ValueError, ServerConfig, max_streams=-1)
  for value in (0, -1, float('inf'), float('nan')):
    utest_exc(ValueError, ServerConfig, stream_max_duration=value)


@utest_run
def test_stalled_stream_does_not_occupy_ordinary_worker() -> None:
  app = App()
  with running_server(app, max_streams=1, conn_timeout=0.1) as (server, records):
    with create_connection((server.host, server.port), timeout=2) as socket:
      socket.sendall(b'GET /large HTTP/1.1\r\nHost: localhost\r\n\r\n')
      assert socket.recv(4096) # Headers are sent before the producer is run.
      utest_val((200, b'small'), get(server, '/small'))
      utest_val(True, app.bodies[0].closed.wait(2))
      utest_val((200, b'firstsecond'), get(server, '/finite'))
  utest_val([200, 200, 200], [record['s'] for record in records])


@utest_run
def test_idle_pool_does_not_retain_completed_request() -> None:
  released = Event()

  class RetainedBody(Body):
    def __init__(self, request:Request) -> None:
      super().__init__()
      self.request = request
    def __del__(self) -> None: released.set()

  class LifetimeApp(App):
    @allow_public
    def handle_request(self, request:Request) -> Response:
      self.request_ref = ref(request)
      return Response(body=RetainedBody(request))

  app = LifetimeApp()
  with running_server(app, max_streams=1) as (server, _):
    utest_val((200, b'firstsecond'), get(server, '/finite'))
    utest_val(True, released.wait(1))
    utest_val(None, app.request_ref())


@utest_run
def test_stream_watchdog_distinguishes_channel_waits_from_hung_iterators() -> None:
  'Run process-exit tests in isolation; an intentional channel wait must not trigger application hang recovery.'
  for mode in ('channel', 'next', 'close'):
    script = '''
from socket import create_connection
from threading import Event, Thread
from pithy.web.app import WebApp
from pithy.web.auth import allow_public
from pithy.web.response import Response
from pithy.web.server import ServerConfig, WebServer
from pithy.web.sse import SseChannel, SseResponse

def chunks():
  while True: pass
  yield b'unreachable'

class UnstartedBody:
  def __iter__(self): return self
  def __next__(self): return b'unreachable'
  def close(self):
    while True: pass

class App(WebApp):
  @allow_public
  def handle_request(self, request):
    if MODE == 'close': return Response(body=UnstartedBody())
    return Response(body=chunks()) if MODE == 'next' else SseResponse(SseChannel())

server = WebServer(app=App(), config=ServerConfig(host='127.0.0.1', num_threads=1, max_streams=1,
  worker_warn_after=0.02, worker_exit_after=0.05, stream_max_duration=0.1, log_access=False))
def stop():
  Event().wait(0.3)
  server.shutdown()
Thread(target=stop).start()
client = create_connection((server.host, server.port))
client.sendall(b'METHOD / HTTP/1.1\\r\\nHost: localhost\\r\\n\\r\\n')
server.serve_forever()
'''.replace('MODE', repr(mode)).replace('METHOD', 'HEAD' if mode == 'close' else 'GET')
    result = run([executable, '-c', script], capture_output=True, text=True, timeout=5)
    hung = mode != 'channel'
    utest_val(1 if hung else 0, result.returncode, result.stdout + result.stderr)
    utest_val('', result.stderr)
    utest_val(hung, 'Application exceeded duration threshold' in result.stdout)
    if hung:
      records = [loads(line) for line in result.stdout.splitlines()]
      fatal = next(record for record in records if record['_'] == 'Application exceeded duration threshold; exiting process.')
      utest_val('/', fatal['path'])
      utest_val('HEAD' if mode == 'close' else 'GET', fatal['method'])
    if not hung: utest_val(False, 'Worker exceeded duration threshold' in result.stdout)
