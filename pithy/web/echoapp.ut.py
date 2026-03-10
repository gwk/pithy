# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import requests
from utest import utest, utest_run
from utest.proctest import TestProcess


@utest_run
def _() -> None:
  'Test EchoApp, which exercises the basics of WebServer, WebApp, and TestProcess.'

  with TestProcess(['python', '-m', 'pithy.web.echoapp'], merge_stderr=True) as server_proc:

    m = server_proc.wait_for_pattern(r'"url":"(http://localhost:\d+)"')
    base_url = m.group(1)

    def fetch(path:str) -> str:
      'Fetch a path from the test server and return the response body as a string.'
      resp = requests.get(f'{base_url}{path}', timeout=2)
      resp.raise_for_status()
      return resp.text

    # Basic path echo.
    utest('GET: /', fetch, '/')
    utest('GET: /hello', fetch, '/hello')
    utest('GET: /a/b/c', fetch, '/a/b/c')

    # Path with query string.
    utest('GET: /search?q=test', fetch, '/search?q=test')
    utest('GET: /multi?a=1&b=2', fetch, '/multi?a=1&b=2')

    # Verify the server process is still healthy.
    _ = server_proc.flush_merged()
