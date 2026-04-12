# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import requests
from utest import utest, utest_run
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

    # Verify the server process is still healthy.
    _ = server_proc.flush_merged()
