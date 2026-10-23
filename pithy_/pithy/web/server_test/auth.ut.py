# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Lifecycle order over a real connection: check_request precedes authenticate, which precedes routing and authorization,
and an unauthorized request is refused before its body is read.
'''

from socket import create_connection
from sys import argv, executable

import requests
from pithy.web.app import AppDestination, WebApp
from pithy.web.auth import allow_public, Privileges, requires_privileges, SameOriginCheck
from pithy.web.endpoint import Endpoint
from pithy.web.errors import UnauthorizedError
from pithy.web.request import Request
from pithy.web.response import Response
from pithy.web.router import RouterApp
from pithy.web.server import ServerConfig, WebServer
from utest import utest, utest_run
from utest.proctest import TestProcess


class OpenEndpoint(Endpoint):
  @allow_public
  def get(self, request:Request, fields:None) -> Response:
    return Response(body=f'open:{bool(request.privileges)}', media_type='text/plain')


class PrivateEndpoint(Endpoint):
  max_body_bytes = 64
  class Post:
    name:str
  @requires_privileges('read')
  def get(self, request:Request, fields:None) -> Response: return Response(body='private', media_type='text/plain')
  @requires_privileges('write')
  def post(self, request:Request, fields:Post) -> Response: return Response(body=f'posted:{fields.name}', media_type='text/plain')


class LifecycleApp(RouterApp):

  same_origin:SameOriginCheck # Set once the server has bound its port.

  def __init__(self) -> None:
    super().__init__({'/open': OpenEndpoint, '/private': PrivateEndpoint})

  def check_request(self, request:Request) -> None:
    self.same_origin(request)

  def authenticate(self, request:Request) -> Privileges:
    credential = request.headers.get('authorization', '')
    if not credential: return frozenset()
    if credential == 'Bearer broken': return frozenset({'read'})
    if credential == 'Bearer reader': return frozenset({'authenticated', 'read'})
    if credential == 'Bearer writer': return frozenset({'authenticated', 'read', 'write'})
    raise UnauthorizedError('Invalid token.')


  def finish_response(self, request:Request, response:Response) -> Response:
    response.headers['x-finished'] = 'yes'
    return response



class TrackedAppDestination(AppDestination):
  def get_handler(self, request:Request) -> WebApp:
    request.ctx['events'].append('get_handler')
    return super().get_handler(request)


class SimpleApp(WebApp):
  'Exercise the fixed authorization step without a router.'

  def check_request(self, request:Request) -> None:
    request.ctx['events'] = ['check_request']

  def authenticate(self, request:Request) -> Privileges:
    request.ctx['events'].append('authenticate')
    credential = request.headers.get('authorization', '')
    if not credential: return frozenset()
    if credential == 'Bearer reader': return frozenset({'authenticated', 'read'})
    return frozenset({'authenticated'})

  def resolve_destination(self, request:Request) -> AppDestination:
    request.ctx['events'].append('resolve_destination')
    destination = super().resolve_destination(request)
    return TrackedAppDestination(required_privileges=destination.required_privileges, app=self)

  def prepare_for_request(self, request:Request) -> None:
    request.ctx['events'].append('prepare_for_request')
    request.read_body(max_bytes=16)

  @requires_privileges('read')
  def handle_request(self, request:Request) -> Response:
    request.ctx['events'].append('handle_request')
    return Response(body='ok')

  def finish_response(self, request:Request, response:Response) -> Response:
    request.ctx['events'].append('finish_response')
    response.headers['x-events'] = ','.join(request.ctx['events'])
    return response


def test_simple_app() -> None:
  with TestProcess([executable, __file__, 'serve-simple'], merge_stderr=True) as server_proc:
    match = server_proc.wait_for_pattern(r'"url":"(http://localhost:\d+)"')
    base_url = match.group(1)
    for credential, status in (('', 401), ('Bearer other', 403), ('Bearer reader', 200)):
      headers = {'authorization': credential}
      if status == 200: headers['connection'] = 'close' # Release the single worker before the next connection.
      response = requests.post(base_url, data=b'x', headers=headers, timeout=2)
      utest(status, int, response.status_code)
      events = ['check_request', 'authenticate', 'resolve_destination']
      if status == 200: events += ['get_handler', 'prepare_for_request', 'handle_request']
      events.append('finish_response')
      utest(','.join(events), lambda: response.headers['x-events'])
      if status != 200: utest('close', lambda: response.headers.get('connection'))

    # Authorization also precedes 100 Continue for a simple app.
    port = int(base_url.rsplit(':', 1)[1])
    with create_connection(('localhost', port), timeout=2) as sock:
      sock.sendall((f'POST / HTTP/1.1\r\nHost: localhost:{port}\r\n'
        'Expect: 100-continue\r\nContent-Length: 1\r\n\r\n').encode('ascii'))
      with sock.makefile('rb') as stream:
        utest(401, lambda: int(stream.readline().split()[1]))
    _ = server_proc.flush_merged()


def serve() -> None:
  app = LifecycleApp()
  server = WebServer(app=app, config=ServerConfig(num_threads=1))
  app.same_origin = SameOriginCheck(server.url)
  server.serve_forever()


def test_lifecycle() -> None:

  with TestProcess([executable, __file__, 'serve'], merge_stderr=True) as server_proc:
    m = server_proc.wait_for_pattern(r'"url":"(http://localhost:\d+)"')
    base_url = m.group(1)

    def get(path:str, **headers:str) -> tuple[int,str]:
      resp = requests.get(f'{base_url}{path}', headers=headers, timeout=2)
      return (resp.status_code, resp.text)

    def post(path:str, data:bytes, **headers:str) -> tuple[int,str,str|None]:
      resp = requests.post(f'{base_url}{path}', data=data, timeout=2,
        headers={'content-type':'application/x-www-form-urlencoded', **headers})
      return (resp.status_code, resp.text, resp.headers.get('connection'))

    utest((200, 'open:False'), get, '/open')
    utest((200, 'open:True'), get, '/open', authorization='Bearer reader')
    utest(401, lambda: get('/private')[0])
    utest((200, 'private'), get, '/private', authorization='Bearer reader')
    # authenticate precedes routing: an invalid credential is refused even for an unknown path.
    utest(401, lambda: get('/private', authorization='Bearer bogus')[0])
    utest(401, lambda: get('/missing', authorization='Bearer bogus')[0])
    utest(401, lambda: get('/open', authorization='Bearer bogus')[0])
    for path in ('/open', '/private', '/missing'):
      utest(500, lambda: get(path, authorization='Bearer broken')[0])
    utest(404, lambda: get('/missing')[0])
    # check_request precedes authenticate: a valid credential does not rescue a cross-origin request, even to a public route.
    utest(421, lambda: get('/open', authorization='Bearer reader', host='evil.example')[0])
    utest(403, lambda: get('/open', origin='https://evil.example')[0])
    utest(403, lambda: get('/open', **{'sec-fetch-site':'cross-site'})[0])
    navigation = {'sec-fetch-site':'cross-site', 'sec-fetch-mode':'navigate', 'sec-fetch-dest':'document'}
    utest(200, lambda: get('/open', **navigation)[0]) # An inbound link or a sign-in redirect is admitted.
    utest(401, lambda: get('/private', **navigation)[0]) # An admitted navigation is still subject to authorization.
    def status_and_finish_header(credential:str) -> tuple[int,str|None]:
      response = requests.get(f'{base_url}/private', headers={'authorization': credential}, timeout=2)
      return response.status_code, response.headers.get('x-finished')

    for credential, expected in (('', 401), ('Bearer reader', 200)):
      utest((expected, 'yes'), status_and_finish_header, credential)
    # Authorization precedes the body: a refused POST is answered before the body is read, so the connection closes.
    status, body, connection = post('/private', b'name=x')
    utest(401, int, status)
    utest('close', str, connection)
    status, body, connection = post('/private', b'name=x', authorization='Bearer reader')
    utest(403, int, status)
    utest('close', str, connection)
    status, body, connection = post('/private', b'name=x', authorization='Bearer writer')
    utest((200, 'posted:x', None), tuple, (status, body, connection))

    # Send only headers: authorization must refuse the upload without first sending 100 Continue or waiting for a body.
    authority = base_url.removeprefix('http://')
    port = int(authority.rsplit(':', 1)[1])
    for expected, credential in ((401, ''), (403, 'Bearer reader')):
      with create_connection(('localhost', port), timeout=2) as sock:
        sock.sendall((f'POST /private HTTP/1.1\r\nHost: {authority}\r\n'
          f'Authorization: {credential}\r\nExpect: 100-continue\r\nContent-Length: 6\r\n'
          'Content-Type: application/x-www-form-urlencoded\r\n\r\n').encode('ascii'))
        with sock.makefile('rb') as stream:
          utest(expected, lambda: int(stream.readline().split()[1]))
          response_headers = []
          while line := stream.readline():
            if line == b'\r\n': break
            response_headers.append(line.lower())
          utest(True, lambda: b'connection: close\r\n' in response_headers)

    _ = server_proc.flush_merged()


if len(argv) > 1 and argv[1] == 'serve':
  serve()
elif len(argv) > 1 and argv[1] == 'serve-simple':
  WebServer(app=SimpleApp(), config=ServerConfig(num_threads=1)).serve_forever()
else:
  utest_run(test_lifecycle)
  utest_run(test_simple_app)
