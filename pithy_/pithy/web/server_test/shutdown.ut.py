# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from selectors import DefaultSelector, SelectorKey
from threading import Event, Thread
from unittest.mock import patch

from pithy.web.app import WebApp
from pithy.web.server import ServerConfig, WebServer
from utest import utest_run, utest_val


@utest_run
def test_shutdown_wakes_listener() -> None:
  'Shutdown wakes an idle listener, including a wakeup sent just before select begins.'
  for pause_before_select in (False, True):
    server = WebServer(app=WebApp(), config=ServerConfig(host='127.0.0.1', num_threads=1, log_access=False))
    selecting = Event()
    proceed = Event()
    errors:list[BaseException] = []
    with DefaultSelector() as selector:
      real_select = selector.select

      def select(timeout:float|None=None) -> list[tuple[SelectorKey,int]]:
        selecting.set()
        if pause_before_select: assert proceed.wait(3)
        return real_select(timeout)

      def serve() -> None:
        try: server.serve_forever()
        except BaseException as error: errors.append(error)

      with patch('pithy.web.server.DefaultSelector', return_value=selector), \
       patch.object(selector, 'select', side_effect=select), patch('pithy.web.server.logI'):
        thread = Thread(target=serve)
        thread.start()
        try:
          assert selecting.wait(3)
          server.shutdown()
          server.shutdown()
          if pause_before_select:
            # Repeated requests must not fill the wakeup buffer while the serving thread is delayed.
            for _ in range(100_000): server.shutdown()
          proceed.set()
          thread.join(timeout=0.5)
          utest_val(False, thread.is_alive())
        finally:
          proceed.set()
          try: server.shutdown()
          finally: thread.join(timeout=3)
        utest_val([], errors)
        utest_val(-1, server._socket.fileno())


@utest_run
def test_shutdown_before_start() -> None:
  server = WebServer(app=WebApp(), config=ServerConfig(host='127.0.0.1', num_threads=1))
  server.shutdown()
  server.shutdown()
  utest_val(-1, server._socket.fileno())  # Shutdown before serving closes the listener immediately.
  with patch('pithy.web.server.logI'): server.serve_forever()
  server.shutdown()
  utest_val(-1, server._socket.fileno())
