# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from http import HTTPStatus
from io import BufferedReader
from os import mkdir
from tempfile import TemporaryDirectory
from time import time

from pithy.http import format_header_date
from pithy.web.errors import ResponseError
from pithy.web.files import compute_local_path, ext_media_types, FilesApp, FilesHandler
from pithy.web.request import Request
from pithy.web.response import Response
from pithy.web.router import Router
from utest import utest, utest_exc, utest_run, utest_val


def _request(path:str, headers:dict[str,str]|None=None) -> Request:
  return Request(method='GET', scheme='http', host='localhost', port=80,
    path=path, query_str='', headers=headers or {}, client_addr=('127.0.0.1', 0), content_length=None)


def _serve(app:FilesApp, path:str, headers:dict[str,str]|None=None) -> Response:
  'Build a GET request for `path`, serve it through `app`, and return the response with its body closed.'
  response = app.handle_request(_request(path, headers))
  if isinstance(response.body, BufferedReader): response.body.close()
  return response


@utest_run
def _() -> None:
  'FilesApp: prevent_client_caching adds no-cache headers to served responses.'
  with TemporaryDirectory() as tmp:
    with open(f'{tmp}/a.txt', 'w') as f: f.write('hello')

    caching = FilesApp(local_dir=tmp)
    utest_val(False, 'Cache-Control' in _serve(caching, '/a.txt').headers,
      desc='default FilesApp does not set Cache-Control')

    no_caching = FilesApp(local_dir=tmp, prevent_client_caching=True)
    no_cache_headers = _serve(no_caching, '/a.txt').headers
    utest_val(True, 'Cache-Control' in no_cache_headers, desc='prevent_client_caching sets Cache-Control')
    utest_val(True, 'Pragma' in no_cache_headers, desc='prevent_client_caching sets Pragma')


@utest_run
def _() -> None:
  'FilesApp: guess_media_type maps known extensions and falls back to the default.'
  app = FilesApp(local_dir='.')
  utest('text/plain', app.guess_media_type, 'a.txt')
  utest('text/plain', app.guess_media_type, 'no_extension') # Falls back to the '' default.


@utest_run
def _() -> None:
  'ext_media_types is overridable as a class attribute by both FilesApp and FilesHandler subclasses.'
  custom_media_types = {**ext_media_types, '.dat': 'application/x-custom'}

  class CustomApp(FilesApp):
    ext_media_types = custom_media_types

  utest('application/x-custom', CustomApp(local_dir='.').guess_media_type, 'a.dat')
  utest('text/plain', FilesApp(local_dir='.').guess_media_type, 'a.dat') # The shared default is unaffected by the override.

  with TemporaryDirectory() as tmp:
    with open(f'{tmp}/a.dat', 'w') as f: f.write('data')

    class CustomHandler(FilesHandler):
      local_dir = tmp
      ext_media_types = custom_media_types

    request = _request('/static/a.dat')
    response = Router({'/static/{subpath:path}': CustomHandler}).resolve_handler(request).handle_request(request)
    if isinstance(response.body, BufferedReader): response.body.close()
    utest_val('application/x-custom', response.headers.get('content-type'), desc='mounted handler uses the override')


@utest_run
def _() -> None:
  'FilesHandler: mounted under a router prefix, maps the captured subpath into local_dir.'
  with TemporaryDirectory() as tmp:
    mkdir(f'{tmp}/sub')
    with open(f'{tmp}/sub/app.css', 'w') as f: f.write('body{}')

    class Mounted(FilesHandler):
      local_dir = tmp

    router = Router({'/static/{subpath:path}': Mounted})

    def content_type(path:str) -> str|None:
      request = _request(path)
      response = router.resolve_handler(request).handle_request(request)
      if isinstance(response.body, BufferedReader): response.body.close()
      value = response.headers.get('content-type')
      return value if isinstance(value, str) else None

    utest('text/css;charset=utf-8', content_type, '/static/sub/app.css')

    # A directory without a trailing slash redirects within the mount prefix, using the full request path (not the subpath).
    # The response is built via Response.from_error, exactly as the server does, so the lowercase-header rule is exercised.
    def redirect_location(path:str) -> object:
      request = _request(path)
      handler = router.resolve_handler(request)
      try: handler.handle_request(request)
      except ResponseError as exc:
        utest_val(HTTPStatus.MOVED_PERMANENTLY, exc.status, desc='directory redirect status')
        return Response.from_error(exc, method='GET').headers.get('location')
      return None

    utest('/static/sub/', redirect_location, '/static/sub')


@utest_run
def _() -> None:
  'FilesApp: conditional requests emit validators and honor If-None-Match and If-Modified-Since.'
  with TemporaryDirectory() as tmp:
    with open(f'{tmp}/a.txt', 'w') as f: f.write('hello')
    app = FilesApp(local_dir=tmp)

    # An initial response carries the ETag and Last-Modified validators.
    resp = _serve(app, '/a.txt')
    etag = resp.headers.get('etag')
    utest_val(True, isinstance(etag, str) and etag.startswith('"'), desc='etag present and quoted')
    utest_val(True, 'last-modified' in resp.headers, desc='last-modified present')
    assert isinstance(etag, str)

    # A matching If-None-Match yields 304 with no body; a non-matching one yields 200.
    r304 = _serve(app, '/a.txt', headers={'if-none-match': etag})
    utest_val(HTTPStatus.NOT_MODIFIED, r304.status, desc='matching etag yields 304')
    utest_val(None, r304.body, desc='304 has no body')
    utest_val(etag, r304.headers.get('etag'), desc='304 echoes the etag')
    utest_val(HTTPStatus.OK, _serve(app, '/a.txt', headers={'if-none-match': '"nope"'}).status,
      desc='non-matching etag yields 200')

    # If-Modified-Since: a future date means the client copy is current (304); the epoch means it is stale (200).
    utest_val(HTTPStatus.NOT_MODIFIED, _serve(app, '/a.txt', headers={'if-modified-since': format_header_date(time() + 3600)}).status,
      desc='future If-Modified-Since yields 304')
    utest_val(HTTPStatus.OK, _serve(app, '/a.txt', headers={'if-modified-since': format_header_date(0)}).status,
      desc='epoch If-Modified-Since yields 200')


@utest_run
def _() -> None:
  'FilesApp: prevent_client_caching suppresses validators and 304s (no-store development mode).'
  with TemporaryDirectory() as tmp:
    with open(f'{tmp}/a.txt', 'w') as f: f.write('hello')
    app = FilesApp(local_dir=tmp, prevent_client_caching=True)

    utest_val(False, 'etag' in _serve(app, '/a.txt').headers, desc='no etag when prevent_client_caching')
    utest_val(HTTPStatus.OK, _serve(app, '/a.txt', headers={'if-none-match': '"whatever"'}).status,
      desc='no 304 when prevent_client_caching')


@utest_run
def _() -> None:
  'compute_local_path: rejects paths that escape local_dir via `..`.'
  utest('/root/a.txt', compute_local_path, local_dir='/root', norm_path='/a.txt', map_bare_names_to_html=False)
  utest_exc(ResponseError, compute_local_path, local_dir='/root', norm_path='/../etc', map_bare_names_to_html=False)
