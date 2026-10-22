# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from http import HTTPStatus
from http.client import HTTPConnection
from io import BufferedReader
from sys import argv, executable
from urllib.parse import urlsplit

import requests
from pithy.web.app import WebApp
from pithy.web.errors import BadRequestError, ResponseError
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


  def error_response(self, request:Request, error:ResponseError) -> Response|None:
    if request.path == '/error-hook-raises': raise RuntimeError('error hook failed')
    if request.path == '/error-hook-defers': return None
    response = super().error_response(request, error)
    assert response is not None
    response.headers['x-error-hook'] = error.status.phrase
    return response


  def finish_response(self, request:Request, response:Response) -> Response:
    if request.path == '/finish-failed-file': raise RuntimeError('finish failed')
    if request.path == '/finish-rejected-file': raise BadRequestError('finish rejected')
    if request.path == '/finish-shared-file': return Response(body=response.body)
    if request.path == '/finish-new-file': return file_response(Response)
    if request.path in ('/finish-mutated-file', '/finish-mutated-failed-file'):
      response.body = file_response(Response).body
      if request.path == '/finish-mutated-failed-file': raise RuntimeError('finish failed after replacing body')
    if request.path == '/finish-text': return Response(body='replacement')
    response.headers['x-finish-hook'] = 'finished'
    return response


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
      case '/error-hook-raises' | '/error-hook-defers': raise BadRequestError('bad input')
      case '/raise-bad-request.json' | '/raise-bad-request.css': raise BadRequestError('bad input')
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
      case path if path.startswith('/finish-'): return file_response(Response)
      case '/broken-file-response': return file_response(BrokenResponse)
      case '/file-state': return Response(body=','.join(str(file.closed) for file in file_bodies))
      case _: return Response(body='not found', status=HTTPStatus.NOT_FOUND, media_type='text/plain')



def serve() -> None:
  server = WebServer(app=ServerExceptionTestApp(), config=ServerConfig(num_threads=1, prevent_client_caching=True))
  server.serve_forever()


def get_status_body(base_url:str, path:str) -> tuple[int,str]:
  resp = requests.get(f'{base_url}{path}', timeout=2)
  return (resp.status_code, resp.text)


def get_status_hooks(base_url:str, path:str) -> tuple[int,str|None,str|None]:
  'The status and the headers set by the error_response and finish_response hooks, showing which the response passed through.'
  resp = requests.get(f'{base_url}{path}', timeout=2)
  return (resp.status_code, resp.headers.get('x-error-hook'), resp.headers.get('x-finish-hook'))


def get_error_details(base_url:str, path:str) -> tuple[int,str|None,str,str|None,str|None]:
  '''
  The status, content type, body and hook headers of an error response.
  Helpers return tuples rather than Response objects: a live Response holds its keep-alive socket open,
  and the single worker thread would then wait out the connection timeout before serving the next request.
  '''
  resp = requests.get(f'{base_url}{path}', timeout=2)
  return (resp.status_code, resp.headers.get('content-type'), resp.text, resp.headers.get('x-error-hook'),
    resp.headers.get('x-finish-hook'))


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

    # An unhandled exception produces a bare 500 that bypasses both hooks.
    utest((500, 'Internal Server Error'), get_status_body, base_url, '/raise')
    utest((500, None, None), get_status_hooks, base_url, '/raise')
    response = requests.get(f'{base_url}/ok', headers={'Connection': 'close'}, timeout=2)
    utest('no-cache, no-store, must-revalidate', response.headers.get, 'cache-control')
    utest((200, None, 'finished'), get_status_hooks, base_url, '/ok') # A normal response passes through finish_response only.
    # NotImplementedError: 501 through the error hook, with a fixed reason that does not leak the exception message.
    status, body = get_status_body(base_url, '/raise-not-implemented')
    utest(501, int, status)
    utest(True, lambda b: 'Not Implemented' in b and 'not yet' not in b, body)
    utest((501, 'Not Implemented', 'finished'), get_status_hooks, base_url, '/raise-not-implemented')
    utest((200, 'ok'), get_status_body, base_url, '/ok')
    utest((501, 'Not Implemented', 'finished'), get_status_hooks, base_url, '/raise-not-implemented-empty')
    utest((200, 'ok'), get_status_body, base_url, '/ok')
    # BadRequestError (a ResponseError): 400 through the error hook, with a plain text body containing the reason.
    status, body = get_status_body(base_url, '/raise-bad-request')
    utest(400, int, status)
    utest(True, lambda b: 'bad input' in b, body)
    utest((400, 'Bad Request', 'finished'), get_status_hooks, base_url, '/raise-bad-request')
    utest((200, 'ok'), get_status_body, base_url, '/ok')
    # An app hook that raises or defers falls through to the plain text renderer, keeping the status; finish still runs.
    for path in ('/error-hook-raises', '/error-hook-defers'):
      utest((400, 'text/plain;charset=utf-8', '400: bad input.\n', None, 'finished'), get_error_details, base_url, path)
    utest((200, 'ok'), get_status_body, base_url, '/ok')
    # The path extension selects the renderer: JSON for .json, plain text for any file-like extension.
    utest((400, 'application/problem+json', '{"detail":"bad input","status":400,"title":"Bad Request"}\n', 'Bad Request', 'finished'),
      get_error_details, base_url, '/raise-bad-request.json')
    utest((400, 'text/plain;charset=utf-8', '400: bad input.\n', 'Bad Request', 'finished'),
      get_error_details, base_url, '/raise-bad-request.css')
    utest((200, 'ok'), get_status_body, base_url, '/ok')
    # BodyTooLargeError: 413 through the error hook with connection close; a small body still succeeds.
    utest((200, 'read ok'), post_status_body, base_url, '/read-small-body', b'tiny')
    response = requests.post(f'{base_url}/read-small-body', data=b'0123456789ABCDEF', timeout=2)
    utest(413, int, response.status_code)
    utest(True, lambda: 'Content Too Large' in response.text)
    utest('Content Too Large', response.headers.get, 'x-error-hook')
    utest('finished', response.headers.get, 'x-finish-hook')
    utest('close', response.headers.get, 'connection')
    utest((200, 'ok'), get_status_body, base_url, '/ok')
    # A broken Response causes _send_response to fail; the server closes the connection without replying.
    utest_exc(requests.exceptions.ConnectionError, get_status_body, base_url, '/broken-response')
    utest((200, 'ok'), get_status_body, base_url, '/ok')
    utest(200, lambda: requests.head(f'{base_url}/file', timeout=2).status_code)
    utest((200, 'True'), get_status_body, base_url, '/file-state')
    utest_exc(requests.exceptions.ConnectionError, get_status_body, base_url, '/broken-file-response')
    utest((200, 'True,True'), get_status_body, base_url, '/file-state')
    # A failing finish hook closes the discarded file response and bypasses both hooks for the fallback.
    for path in ('/finish-failed-file', '/finish-rejected-file'):
      utest((500, None, None), get_status_hooks, base_url, path)
    utest((200, 'True,True,True,True'), get_status_body, base_url, '/file-state')

    # Body ownership follows the file, including sharing across responses and replacement in place.
    with open(__file__) as source: expected_body = source.read()
    count = 4
    for path, added in (('/finish-shared-file', 1), ('/finish-new-file', 2), ('/finish-mutated-file', 2)):
      utest((200, expected_body), get_status_body, base_url, path)
      count += added
      utest((200, ','.join(['True'] * count)), get_status_body, base_url, '/file-state')
    utest((200, 'replacement'), get_status_body, base_url, '/finish-text')
    count += 1
    utest((200, ','.join(['True'] * count)), get_status_body, base_url, '/file-state')
    utest((500, 'Internal Server Error'), get_status_body, base_url, '/finish-mutated-failed-file')
    count += 2
    utest((200, ','.join(['True'] * count)), get_status_body, base_url, '/file-state')

    _ = server_proc.flush_merged()


if len(argv) > 1 and argv[1] == 'serve':
  serve()
else:
  utest_run(test_server_exceptions)
