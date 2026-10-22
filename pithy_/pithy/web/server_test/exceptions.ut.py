# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from http import HTTPStatus
from http.client import HTTPConnection
from io import BufferedReader
from sys import argv, executable
from urllib.parse import urlsplit

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


file_bodies:list[BufferedReader] = []


def file_response(cls:type[Response]) -> Response:
  file = open(__file__, 'rb')
  try: response = cls(body=file)
  except:
    file.close()
    raise
  file_bodies.append(file)
  return response



class ServerExceptionTestApp(WebApp):

  def resolve_handler(self, request:Request) -> ServerExceptionTestApp:
    if request.path == '/reject-at-resolve': raise BadRequestError('bad input')
    return self


  def prepare_for_request(self, request:Request) -> None:
    if request.path == '/reject-at-prepare': raise BadRequestError('bad input')


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
      case '/reject-partial-body':
        assert request.conn is not None
        chunk = request.conn.read_some(max_bytes=8)
        assert chunk and b'tiny'.startswith(chunk)
        raise BadRequestError('bad input')
      case '/reject-read-body':
        request.read_body(max_bytes=8)
        raise BadRequestError('bad input')
      case '/broken-response': return BrokenResponse(body='unreachable', media_type='text/plain')
      case '/file': return file_response(Response)
      case '/broken-file-response': return file_response(BrokenResponse)
      case '/file-state': return Response(body=','.join(str(file.closed) for file in file_bodies))
      case _: return Response(body='not found', status=HTTPStatus.NOT_FOUND, media_type='text/plain')



def serve() -> None:
  server = WebServer(app=ServerExceptionTestApp(), config=ServerConfig(num_threads=1, prevent_client_caching=True))
  server.serve_forever()


def get_status_body(base_url:str, path:str) -> tuple[int,str]:
  resp = requests.get(f'{base_url}{path}', timeout=2)
  return (resp.status_code, resp.text)


def post_status_body(base_url:str, path:str, data:bytes) -> tuple[int,str]:
  resp = requests.post(f'{base_url}{path}', data=data, timeout=2)
  return (resp.status_code, resp.text)


def test_error_connections(base_url:str) -> None:
  'Advertise closure for unread bodies, and reuse the connection after a fully consumed request.'
  for path in ('/reject-at-resolve', '/reject-at-prepare', '/raise-bad-request'):
    response = requests.post(f'{base_url}{path}', data=b'tiny', timeout=2)
    utest(400, int, response.status_code)
    utest('close', response.headers.get, 'connection', _utest_label=path)
    utest(True, lambda: 'bad input' in response.text)

  url = urlsplit(base_url)
  assert url.hostname is not None
  conn = HTTPConnection(url.hostname, url.port, timeout=2)
  try:
    # Send only half the declared body so the handler cannot consume it all in one read.
    conn.putrequest('POST', '/reject-partial-body')
    conn.putheader('Content-Length', '8')
    conn.endheaders(b'tiny')
    socket = conn.sock
    assert socket is not None
    response_partial = conn.getresponse()
    utest(400, int, response_partial.status)
    utest('close', response_partial.getheader, 'connection')
    socket.sendall(b'rest') # Let the server finish draining before closing.
    utest(True, lambda: b'bad input' in response_partial.read())
  finally:
    conn.close()

  conn = HTTPConnection(url.hostname, url.port, timeout=2)
  try:
    conn.request('POST', '/reject-read-body', body=b'tiny')
    socket = conn.sock
    assert socket is not None
    response_read = conn.getresponse()
    utest(400, int, response_read.status)
    utest(None, response_read.getheader, 'connection')
    utest(True, lambda: b'bad input' in response_read.read())
    conn.request('POST', '/read-small-body', body=b'tiny')
    utest(True, lambda: conn.sock is socket) # A reconnect must not hide a failure to reuse the socket.
    response_ok = conn.getresponse()
    utest(200, int, response_ok.status)
    utest(b'read ok', response_ok.read)
  finally:
    conn.close()


def test_empty_request_connections(base_url:str) -> None:
  'Complete empty requests without requiring handlers to read them, preserving explicit body reads and close requests.'
  url = urlsplit(base_url)
  assert url.hostname is not None
  for method, path, headers, status, body in (
    ('GET', '/ok', {}, 200, b'ok'),
    ('HEAD', '/ok', {}, 200, b''),
    ('POST', '/ok', {'Content-Length': '0'}, 200, b'ok'),
    ('GET', '/read-small-body', {}, 200, b'read ok'),
    ('POST', '/read-small-body', {'Content-Length': '0'}, 200, b'read ok'),
    ('GET', '/reject-at-resolve', {}, 400, None),
    ('GET', '/reject-at-prepare', {}, 400, None),
    ('GET', '/raise-bad-request', {}, 400, None),
  ):
    conn = HTTPConnection(url.hostname, url.port, timeout=2)
    try:
      conn.request(method, path, headers=headers)
      socket = conn.sock
      assert socket is not None
      response = conn.getresponse()
      utest(status, int, response.status)
      utest(None, response.getheader, 'connection', _utest_label=f'{method} {path}')
      received = response.read()
      if body is not None: utest(body, bytes, received)
      else: utest(True, lambda: b'bad input' in received)
      conn.request('GET', '/ok', headers={'Connection': 'close'})
      utest(True, lambda: conn.sock is socket, _utest_label=f'{method} {path}')
      response = conn.getresponse()
      utest(200, int, response.status)
      utest('close', response.getheader, 'connection')
      utest(b'ok', response.read)
    finally:
      conn.close()

  # Framing, not the method or Content-Length alone, determines whether a request is empty.
  for headers in ({}, {'Transfer-Encoding': 'chunked'}, {'Transfer-Encoding': 'chunked', 'Content-Length': '0'}):
    conn = HTTPConnection(url.hostname, url.port, timeout=2)
    try:
      conn.request('GET', '/ok', body=b'tiny', headers=headers, encode_chunked='Transfer-Encoding' in headers)
      response = conn.getresponse()
      utest(200, int, response.status)
      utest('close', response.getheader, 'connection')
      utest(b'ok', response.read)
    finally:
      conn.close()


def test_server_exceptions() -> None:
  'Test that request and response exceptions do not kill worker threads.'

  with TestProcess([executable, __file__, 'serve'], merge_stderr=True) as server_proc:
    m = server_proc.wait_for_pattern(r'"url":"(http://localhost:\d+)"')
    base_url = m.group(1)
    test_error_connections(base_url)
    test_empty_request_connections(base_url)

    utest((500, 'Internal Server Error'), get_status_body, base_url, '/raise')
    response = requests.get(f'{base_url}/ok', headers={'Connection': 'close'}, timeout=2)
    utest('no-cache, no-store, must-revalidate', response.headers.get, 'cache-control')
    utest((200, 'ok'), get_status_body, base_url, '/ok')
    # NotImplementedError: 501 with a fixed body that does not leak the exception message.
    utest((501, 'Not Implemented'), get_status_body, base_url, '/raise-not-implemented')
    utest((200, 'ok'), get_status_body, base_url, '/ok')
    utest((501, 'Not Implemented'), get_status_body, base_url, '/raise-not-implemented-empty')
    utest((200, 'ok'), get_status_body, base_url, '/ok')
    # BadRequestError (a ResponseError): 400 with a plain text body containing the reason.
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
    utest(200, lambda: requests.head(f'{base_url}/file', timeout=2).status_code)
    utest((200, 'True'), get_status_body, base_url, '/file-state')
    utest_exc(requests.exceptions.ConnectionError, get_status_body, base_url, '/broken-file-response')
    utest((200, 'True,True'), get_status_body, base_url, '/file-state')

    _ = server_proc.flush_merged()


if len(argv) > 1 and argv[1] == 'serve':
  serve()
else:
  utest_run(test_server_exceptions)
