# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from textwrap import dedent

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

  with TestProcess(['pithy.web.echoapp'], module=True, merge_stderr=True) as server_proc:

    m = server_proc.wait_for_pattern(r'"url":"(http://localhost:\d+)"')
    base_url = m.group(1)
    host = base_url.split('//')[1]

    def fetch(path:str) -> str:
      'Fetch a path from the test server and return the filtered response.'
      resp = requests.get(f'{base_url}{path}', timeout=2)
      resp.raise_for_status()
      return filter_response(resp.text)

    # Basic path echo.
    utest(dedent(f'''\
      GET: /
      host: {host}'''),
      fetch, '/')

    utest(dedent(f'''\
      GET: /hello
      host: {host}'''),
      fetch, '/hello')

    utest(dedent(f'''\
      GET: /a/b/c
      host: {host}'''),
      fetch, '/a/b/c')

    # Path with query string.
    utest(dedent(f'''\
      GET: /search?q=test
      host: {host}'''),
      fetch, '/search?q=test')

    utest(dedent(f'''\
      GET: /multi?a=1&b=2
      host: {host}'''),
      fetch, '/multi?a=1&b=2')

    def post(path:str, body:str, content_type:str) -> str:
      resp = requests.post(f'{base_url}{path}', data=body.encode(),
        headers={'Content-Type': content_type}, timeout=2)
      resp.raise_for_status()
      return filter_response(resp.text)

    # POST text/plain.
    utest(dedent(f'''\
      POST: /
      content-length: 11
      content-type: text/plain
      host: {host}

      hello world'''),
      post, '/', 'hello world', 'text/plain')

    # POST text/plain with charset suffix.
    utest(dedent(f'''\
      POST: /
      content-length: 11
      content-type: text/plain; charset=utf-8
      host: {host}

      hello world'''),
      post, '/', 'hello world', 'text/plain; charset=utf-8')

    # POST application/x-www-form-urlencoded basic.
    utest(dedent(f'''\
      POST: /
      content-length: 9
      content-type: application/x-www-form-urlencoded
      host: {host}

      name: John'''),
      post, '/', 'name=John', 'application/x-www-form-urlencoded')

    # POST application/x-www-form-urlencoded multiple params.
    utest(dedent(f'''\
      POST: /
      content-length: 16
      content-type: application/x-www-form-urlencoded
      host: {host}

      name: John
      age: 30'''),
      post, '/', 'name=John&age=30', 'application/x-www-form-urlencoded')

    # POST application/x-www-form-urlencoded empty body.
    utest(dedent(f'''\
      POST: /
      content-length: 0
      content-type: application/x-www-form-urlencoded
      host: {host}'''),
      post, '/', '', 'application/x-www-form-urlencoded')

    # POST multipart/form-data with a text field (content-type/content-length filtered: boundary is dynamic).
    def parse_multipart_fields(path:str, fields:dict[str,str]) -> str:
      resp = requests.post(f'{base_url}{path}',
        files={k: (None, v) for k, v in fields.items()}, timeout=2)
      resp.raise_for_status()
      return filter_response(resp.text, ignored_headers_default | {'content-type', 'content-length'})

    utest(dedent(f'''\
      POST: /
      host: {host}

      name: Alice'''),
      parse_multipart_fields, '/', {'name': 'Alice'})

    # POST application/json.
    utest(dedent(f'''\
      POST: /
      content-length: 16
      content-type: application/json
      host: {host}

      key: value'''),
      post, '/', '{"key": "value"}', 'application/json')

    # POST application/json empty object.
    utest(dedent(f'''\
      POST: /
      content-length: 2
      content-type: application/json
      host: {host}'''),
      post, '/', '{}', 'application/json')

    # POST unknown content type.
    utest(dedent(f'''\
      POST: /
      content-length: 5
      content-type: application/octet-stream
      host: {host}

      [unknown content type: application/octet-stream, 5 bytes]'''),
      post, '/', 'hello', 'application/octet-stream')

    # Verify the server process is still healthy.
    _ = server_proc.flush_merged()
