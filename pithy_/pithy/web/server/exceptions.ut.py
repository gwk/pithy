# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from http import HTTPStatus
from sys import argv, executable

import requests
from pithy.web.app import WebApp
from pithy.web.errors import BadRequestError
from pithy.web.request import Request
from pithy.web.response import Response
from pithy.web.server import ServerConfig, WebServer
from utest import utest, utest_exc, utest_run
from utest.proctest import TestProcess


class BrokenResponse(Response):
  'A response that fails before h11 starts sending it.'

  def headers_bytes_list(self) -> list[tuple[bytes,bytes]]:
    raise RuntimeError('broken response')



class ServerExceptionTestApp(WebApp):

  def handle_request(self, request:Request) -> Response:
    match request.path:
      case '/ok': return Response(body='ok', media_type='text/plain')
      case '/read-small-body':
        request.read_body(max_bytes=8)
        return Response(body='read ok', media_type='text/plain')
      case '/raise': raise RuntimeError('handler failed')
      case '/raise-not-implemented': raise NotImplementedError('not yet')
      case '/raise-not-implemented-empty': raise NotImplementedError
      case '/raise-bad-request': raise BadRequestError('bad input')
      case '/broken-response': return BrokenResponse(body='unreachable', media_type='text/plain')
      case _: return Response(body='not found', status=HTTPStatus.NOT_FOUND, media_type='text/plain')



def serve() -> None:
  server = WebServer(app=ServerExceptionTestApp(), config=ServerConfig(num_threads=1))
  server.serve_forever()


def get_status_body(base_url:str, path:str) -> tuple[int,str]:
  resp = requests.get(f'{base_url}{path}', timeout=2)
  return (resp.status_code, resp.text)


def post_status_body(base_url:str, path:str, data:bytes) -> tuple[int,str]:
  resp = requests.post(f'{base_url}{path}', data=data, timeout=2)
  return (resp.status_code, resp.text)


def test_server_exceptions() -> None:
  'Test that request and response exceptions do not kill worker threads.'

  with TestProcess([executable, __file__, 'serve'], merge_stderr=True) as server_proc:
    m = server_proc.wait_for_pattern(r'"url":"(http://localhost:\d+)"')
    base_url = m.group(1)

    utest((500, 'Internal Server Error'), get_status_body, base_url, '/raise')
    utest((200, 'ok'), get_status_body, base_url, '/ok')
    # NotImplementedError: 501 with a fixed body that does not leak the exception message.
    utest((501, 'Not Implemented'), get_status_body, base_url, '/raise-not-implemented')
    utest((200, 'ok'), get_status_body, base_url, '/ok')
    utest((501, 'Not Implemented'), get_status_body, base_url, '/raise-not-implemented-empty')
    utest((200, 'ok'), get_status_body, base_url, '/ok')
    # BadRequestError (a ResponseError): 400 with HTML body containing the reason.
    status, body = get_status_body(base_url, '/raise-bad-request')
    utest(400, int, status)
    utest(True, lambda b: 'bad input' in b, body)
    utest((200, 'ok'), get_status_body, base_url, '/ok')
    # BodyTooLargeError: 413 with connection close; a small body still succeeds.
    utest((200, 'read ok'), post_status_body, base_url, '/read-small-body', b'tiny')
    utest((413, 'Content Too Large'), post_status_body, base_url, '/read-small-body', b'0123456789ABCDEF')
    utest((200, 'ok'), get_status_body, base_url, '/ok')
    # A broken Response causes _send_response to fail; the server closes the connection without replying.
    utest_exc(requests.exceptions.ConnectionError, get_status_body, base_url, '/broken-response')
    utest((200, 'ok'), get_status_body, base_url, '/ok')

    _ = server_proc.flush_merged()


if len(argv) > 1 and argv[1] == 'serve':
  serve()
else:
  utest_run(test_server_exceptions)
