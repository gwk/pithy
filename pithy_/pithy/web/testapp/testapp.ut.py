# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Iterator

import requests
from utest import utest, utest_run, utest_val
from utest.proctest import TestProcess


@utest_run
def _() -> None:
  'Test TestApp router-based dispatch.'

  with TestProcess(['python', '-m', 'pithy.web.testapp'], merge_stderr=True) as server_proc:

    m = server_proc.wait_for_pattern(r'"url":"(http://localhost:\d+)"')
    base_url = m.group(1)

    def fetch(path:str) -> str:
      'Fetch a path and return the response body. Raises on non-200 status.'
      resp = requests.get(f'{base_url}{path}', timeout=2)
      resp.raise_for_status()
      return resp.text

    def fetch_status(path:str) -> int:
      'Fetch a path and return the status code.'
      resp = requests.get(f'{base_url}{path}', timeout=2)
      return resp.status_code

    # Root route.
    utest('hello', fetch, '/')

    # Integer id route.
    utest('id=0', fetch, '/items/0')
    utest('id=11', fetch, '/items/11')
    utest(404, fetch_status, '/items/-1')

    # Non-integer id returns 404.
    utest(404, fetch_status, '/items/abc')

    # String name route.
    utest('name=alice', fetch, '/users/alice')
    utest('name=bob', fetch, '/users/bob')

    # Unmatched path returns 404.
    utest(404, fetch_status, '/nonexistent')
    utest(404, fetch_status, '/items')
    utest(404, fetch_status, '/users')

    form_headers = {'content-type': 'application/x-www-form-urlencoded'}

    def post(body:bytes) -> requests.Response:
      'POST a urlencoded body with a Content-Length header.'
      return requests.post(f'{base_url}/echo', data=body, headers=form_headers, timeout=2)

    def post_chunked(*chunks:bytes) -> requests.Response:
      'POST a urlencoded body using chunked transfer encoding (a generator body sends no Content-Length).'
      def gen() -> Iterator[bytes]:
        yield from chunks
      return requests.post(f'{base_url}/echo', data=gen(), headers=form_headers, timeout=2)

    # EchoBody.max_body_bytes is 32. The streaming body-size cap itself is unit-tested in server/requestconn.ut.py;
    # here we cover the end-to-end happy paths over a real connection, where the server reads the body and replies
    # cleanly. (The oversized case rejects mid-upload and closes the connection, which races the response and the
    # ensuing RST, so it is not asserted over the wire.)

    # Normal (Content-Length) POST within the cap parses the body.
    r = post(b'name=alice')
    utest_val(200, r.status_code)
    utest_val('name=alice', r.text)

    # A declared body over the cap is rejected at construction (before the body is read).
    utest_val(413, post(b'name=' + b'x'*64).status_code)

    # Chunked POST (no Content-Length, so content_length is None) within the cap parses the body end-to-end.
    r = post_chunked(b'na', b'me=', b'alice')
    utest_val(200, r.status_code)
    utest_val('name=alice', r.text)

    # Verify the server process is still healthy.
    _ = server_proc.flush_merged()
