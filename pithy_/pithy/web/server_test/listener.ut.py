# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from http.client import HTTPConnection
from socket import AF_INET, SOCK_STREAM, socket as Socket
from threading import Thread
from unittest.mock import patch

from pithy.web.app import WebApp
from pithy.web.auth import allow_public
from pithy.web.request import Request
from pithy.web.response import Response
from pithy.web.server import ServerConfig, WebServer
from utest import utest, utest_exc, utest_run, utest_val


class PortApp(WebApp):
  'Respond with the port of the request.'

  @allow_public
  def handle_request(self, request:Request) -> Response:
    return Response(body=str(request.port))


def bound_listener() -> Socket:
  'Return a listening TCP socket bound to a free local port.'
  listener = Socket(AF_INET, SOCK_STREAM)
  listener.bind(('127.0.0.1', 0))
  listener.listen()
  return listener


@utest_run
def test_inherited_listener() -> None:
  'The server adopts the port of a supplied listener and closes that descriptor on shutdown.'
  with bound_listener() as listener:
    for _ in range(2): # Successive servers can each take a duplicate of one listener, as across reloads.
      inherited = listener.dup()
      server = WebServer(app=WebApp(), config=ServerConfig(host='127.0.0.1'), listener=inherited)
      utest_val(listener.getsockname()[1], server.port)
      server.shutdown()
      utest(-1, inherited.fileno)


@utest_run
def test_failed_init_closes_listener() -> None:
  with bound_listener() as listener:
    utest_exc(ValueError, WebServer, app=WebApp(), config=ServerConfig(host='127.0.0.1', max_connections=0), listener=listener)
    utest(-1, listener.fileno)


@utest_run
def test_request_port() -> None:
  'Requests report the bound port, both for a dynamically assigned port and for an inherited listener.'
  for inherit in (False, True):
    listener = bound_listener() if inherit else None
    server = WebServer(app=PortApp(), config=ServerConfig(host='127.0.0.1', num_threads=1, log_access=False), listener=listener)
    errors:list[BaseException] = []

    def serve() -> None:
      try: server.serve_forever()
      except BaseException as error: errors.append(error)

    with patch('pithy.web.server.logI'):
      thread = Thread(target=serve)
      thread.start()
      try:
        conn = HTTPConnection(server.host, server.port, timeout=2)
        try:
          conn.request('GET', '/')
          utest(str(server.port).encode(), conn.getresponse().read)
        finally: conn.close()
      finally:
        server.shutdown()
        thread.join(timeout=3)
    utest(False, thread.is_alive)
    utest_val([], errors)
