# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from io import BufferedReader
from tempfile import TemporaryDirectory

from pithy.web.filesapp import FilesApp
from pithy.web.request import Request
from pithy.web.response import Response
from utest import utest, utest_run, utest_val


def _serve(app:FilesApp, path:str) -> Response:
  'Build a GET request for `path`, serve it through `app`, and return the response with its body closed.'
  request = Request(method='GET', scheme='http', host='localhost', port=80,
    path=path, query_str='', headers={}, client_addr=('127.0.0.1', 0), content_length=None)
  response = app.handle_request(request)
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
