# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from socket import create_connection
from subprocess import run
from sys import executable
from threading import Event, get_ident, Lock, Thread
from time import sleep
from typing import Any
from unittest.mock import patch

from pithy.web.app import WebApp
from pithy.web.auth import allow_public
from pithy.web.request import Request
from pithy.web.response import Response
from pithy.web.server import _WorkerState, ServerConfig, WebServer
from utest import utest_exc, utest_run, utest_val


def make_state(started:float, *, phase:Any='application', method:str='', path:str='') -> _WorkerState:
  return _WorkerState('test-worker', ('127.0.0.1', 4321), started, started, Lock(), phase=phase, method=method, path=path)


@utest_run
def test_threshold_validation() -> None:
  for name in ('worker_warn_after', 'worker_exit_after'):
    def configure(value:float|None) -> ServerConfig:
      if name == 'worker_warn_after': return ServerConfig(worker_warn_after=value)
      return ServerConfig(worker_exit_after=value)

    for value in (0, -1, float('inf'), float('-inf'), float('nan')):
      utest_exc(ValueError, configure, value)
    for valid_value in (None, 0.01, 60):
      config = configure(valid_value)
      utest_val(valid_value, getattr(config, name))


@utest_run
def test_warning_threshold_and_assignment_reset() -> None:
  server = WebServer(app=WebApp(), config=ServerConfig(worker_warn_after=10))
  ident = get_ident()
  try:
    with patch('pithy.web.server.monotonic', return_value=100), patch('pithy.web.server.logW') as warning:
      server._check_workers() # Idle workers do not warn.
      warning.assert_not_called()
      state = make_state(91, method='GET', path='/slow')
      server._active_workers[ident] = state
      server._check_workers()
      warning.assert_not_called()
      state.started = 90
      server._check_workers() # Warn at the exact boundary.
      server._check_workers()
      warning.assert_called_once()
      fields = warning.call_args.kwargs
      utest_val('application', fields['phase'])
      utest_val('/slow', fields['path'])
      utest_val(10, fields['elapsed'])
      utest_val(True, any('test_warning_threshold_and_assignment_reset' in line for line in fields['stack']))
      server._active_workers[ident] = make_state(80)
      server._check_workers() # A later assignment on the same thread can warn again.
      utest_val(2, warning.call_count)
      server._active_workers.clear()
      server._check_workers()
      utest_val(2, warning.call_count)
  finally:
    server.shutdown()


@utest_run
def test_fatal_threshold_and_disabled_monitor() -> None:
  for enabled in (False, True):
    server = WebServer(app=WebApp(), config=ServerConfig(worker_warn_after=None, worker_exit_after=20 if enabled else None))
    try:
      server._active_workers[get_ident()] = make_state(80)
      with (patch('pithy.web.server.monotonic', return_value=99) as clock,
       patch('pithy.web.server.logW') as warning, patch('pithy.web.server.logE') as error,
       patch('pithy.web.server.os_exit', side_effect=SystemExit) as exit_process):
        server._check_workers()
        error.assert_not_called()
        exit_process.assert_not_called()
        clock.return_value = 100
        if enabled:
          utest_exc(SystemExit, server._check_workers)
          exit_process.assert_called_once_with(1)
          error.assert_called_once()
          utest_val(20, error.call_args.kwargs['elapsed'])
        else:
          server._check_workers()
          clock.assert_not_called()
          error.assert_not_called()
          exit_process.assert_not_called()
        warning.assert_not_called()
    finally:
      server.shutdown()


class BlockingApp(WebApp):

  def __init__(self) -> None:
    self.started = Event()
    self.release = Event()

  @allow_public
  def handle_request(self, request:Request) -> Response:
    self.started.set()
    assert self.release.wait(5)
    return Response(body='ok')


@utest_run
def test_warning_while_serving_and_shutting_down() -> None:
  'A blocked handler gets a warning when the selector has no traffic, and also while shutdown is waiting for the handler.'
  for during_shutdown in (False, True):
    app = BlockingApp()
    warned = Event()
    errors:list[BaseException] = []
    server = WebServer(app=app, config=ServerConfig(host='127.0.0.1', num_threads=1, log_access=False,
      worker_warn_after=0.02))

    def serve() -> None:
      try: server.serve_forever()
      except BaseException as exc: errors.append(exc)

    with (patch('pithy.web.server.logI'), patch('pithy.web.server.logE') as error,
     patch('pithy.web.server.logW', side_effect=lambda *a, **k: warned.set()) as warning):
      thread = Thread(target=serve)
      thread.start()
      try:
        with create_connection((server.host, server.port), timeout=2) as socket:
          socket.sendall(b'GET /slow?secret=hidden HTTP/1.1\r\nHost: localhost\r\n\r\n')
          assert app.started.wait(2)
          if during_shutdown: server.shutdown()
          assert warned.wait(2)
          fields = warning.call_args.kwargs
          utest_val('application', fields['phase'])
          utest_val('GET', fields['method'])
          utest_val('/slow', fields['path'])
          utest_val(False, 'hidden' in repr(fields))
          utest_val(True, any('handle_request' in line for line in fields['stack']))
          app.release.set()
          received = b''
          while b'\r\n\r\nok' not in received:
            chunk = socket.recv(4096)
            assert chunk
            received += chunk
      finally:
        app.release.set()
        server.shutdown()
        thread.join(3)
      utest_val(False, thread.is_alive())
      utest_val([], errors)
      utest_val({}, server._active_workers)
      warning.assert_called_once()
      error.assert_not_called()


@utest_run
def test_completed_assignment_does_not_exit() -> None:
  'Do not exit if the assignment finished or changed while its stack was being formatted.'
  for reassigned in (False, True):
    server = WebServer(app=WebApp(), config=ServerConfig(worker_warn_after=None, worker_exit_after=10))
    ident = get_ident()
    server._active_workers[ident] = make_state(0)

    def format_and_complete(frame:object) -> list[str]:
      if reassigned: server._active_workers[ident] = make_state(20)
      else: server._active_workers.clear()
      return ['old stack']

    try:
      with (patch('pithy.web.server.monotonic', return_value=20),
       patch('pithy.web.server.format_stack', side_effect=format_and_complete),
       patch('pithy.web.server.logE') as error, patch('pithy.web.server.os_exit') as exit_process):
        server._check_workers()
        error.assert_not_called()
        exit_process.assert_not_called()
    finally:
      server.shutdown()


@utest_run
def test_fatal_exit_in_subprocess() -> None:
  'The watchdog really exits the process when a worker is stuck in a Python infinite loop during shutdown.'
  script = '''
from socket import create_connection
from pithy.web.app import WebApp
from pithy.web.auth import allow_public
from pithy.web.server import ServerConfig, WebServer

class App(WebApp):
  @allow_public
  def handle_request(self, request):
    server.shutdown()
    while True: pass

server = WebServer(app=App(), config=ServerConfig(host='127.0.0.1', num_threads=1,
  worker_warn_after=None, worker_exit_after=0.02, log_access=False))
client = create_connection((server.host, server.port))
client.sendall(b'GET /loop HTTP/1.1\\r\\nHost: localhost\\r\\n\\r\\n')
server.serve_forever()
'''
  result = run([executable, '-c', script], capture_output=True, text=True, timeout=5)
  utest_val(1, result.returncode)
  utest_val('', result.stderr)
  utest_val(True, 'Application exceeded duration threshold; exiting process.' in result.stdout)
  utest_val(True, 'application' in result.stdout)


@utest_run
def test_client_phases_are_not_fatal() -> None:
  'Only time in application code can cause an exit. Time spent on client IO restarts the clock.'
  server = WebServer(app=WebApp(), config=ServerConfig(worker_warn_after=None, worker_exit_after=10))
  try:
    with (patch('pithy.web.server.monotonic', return_value=100), patch('pithy.web.server.logE') as error,
     patch('pithy.web.server.os_exit') as exit_process):
      for phase in ('request_headers', 'request_body', 'response', 'cleanup'):
        server._active_workers[get_ident()] = make_state(0, phase=phase)
        server._check_workers()
      state = make_state(0)
      state.phase_started = 95 # Long assignment, recently returned from a body read.
      server._active_workers[get_ident()] = state
      server._check_workers()
      error.assert_not_called()
      exit_process.assert_not_called()
      state.phase_started = 90
      server._check_workers()
      exit_process.assert_called_once_with(1)
  finally:
    server.shutdown()


class BodyApp(WebApp):

  @allow_public
  def handle_request(self, request:Request) -> Response:
    return Response(body=request.read_body(1024))


@utest_run
def test_slow_clients_do_not_exit() -> None:
  'Clients that trickle headers or a body for longer than `worker_exit_after` do not make the process exit.'
  for head in (b'GET / HTTP/1.1\r\nHost: localhost\r\nX-Long: ',
   b'POST / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\nContent-Length: 40\r\n\r\n'):
    server = WebServer(app=BodyApp(), config=ServerConfig(host='127.0.0.1', num_threads=1, log_access=False,
      worker_warn_after=None, worker_exit_after=0.02))
    with (patch('pithy.web.server.logI'), patch('pithy.web.server.log'),
     patch('pithy.web.server.os_exit') as exit_process):
      thread = Thread(target=server.serve_forever)
      thread.start()
      try:
        with create_connection((server.host, server.port), timeout=5) as socket:
          socket.sendall(head + b'a') # The worker now waits for the client, for longer than the threshold.
          sleep(0.06)
      finally:
        server.shutdown()
        thread.join(5)
      exit_process.assert_not_called()


@utest_run
def test_logging_failure_exits() -> None:
  'If stdout is broken, the monitor exits the process for both warning and fatal reports.'
  for warn_after, exit_after, log_name in ((10, None, 'logW'), (None, 10, 'logE')):
    server = WebServer(app=WebApp(), config=ServerConfig(worker_warn_after=warn_after, worker_exit_after=exit_after))
    server._active_workers[get_ident()] = make_state(0)
    try:
      with (patch('pithy.web.server.monotonic', return_value=100),
       patch(f'pithy.web.server.{log_name}', side_effect=BrokenPipeError) as failing_log,
       patch('pithy.web.server.os_exit') as exit_process):
        server._check_workers()
        failing_log.assert_called_once()
        exit_process.assert_called_once_with(1)
    finally:
      server.shutdown()
