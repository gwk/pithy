# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import requests
from utest import utest, utest_run
from utest.proctest import TestProcess


ignored_headers_default = {'accept', 'accept-encoding', 'connection', 'user-agent'}


def filter_response(text:str, ignored_headers:set[str]=ignored_headers_default) -> str:
  'Filter out ignored headers from the echoapp response text.'
  return '\n'.join(l for l in text.split('\n')
    if ':' not in l or l.split(':')[0].lower() not in ignored_headers)


@utest_run
def _() -> None:
  'Test EchoApp, which exercises the basics of WebServer, WebApp, and TestProcess.'

  with TestProcess(['python', '-m', 'pithy.web.echoapp'], merge_stderr=True) as server_proc:

    m = server_proc.wait_for_pattern(r'"url":"(http://localhost:\d+)"')
    base_url = m.group(1)
    host = base_url.split('//')[1]

    def fetch(path:str) -> str:
      'Fetch a path from the test server and return the filtered response.'
      resp = requests.get(f'{base_url}{path}', timeout=2)
      resp.raise_for_status()
      return filter_response(resp.text)

    # Basic path echo.
    utest(f'GET: /\nhost: {host}', fetch, '/')
    utest(f'GET: /hello\nhost: {host}', fetch, '/hello')
    utest(f'GET: /a/b/c\nhost: {host}', fetch, '/a/b/c')

    # Path with query string.
    utest(f'GET: /search?q=test\nhost: {host}', fetch, '/search?q=test')
    utest(f'GET: /multi?a=1&b=2\nhost: {host}', fetch, '/multi?a=1&b=2')

    def post(path:str, body:str) -> str:
      'Post a body to the test server and return the filtered response.'
      resp = requests.post(f'{base_url}{path}', data=body.encode(), headers={'Content-Type': 'text/plain'}, timeout=2)
      resp.raise_for_status()
      return filter_response(resp.text)

    # POST with body.
    utest(f'POST: /\ncontent-length: 11\ncontent-type: text/plain\nhost: {host}\n\nhello world', post, '/', 'hello world')

    # Verify the server process is still healthy.
    _ = server_proc.flush_merged()
