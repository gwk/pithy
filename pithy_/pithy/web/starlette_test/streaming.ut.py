# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import asyncio
from collections.abc import Generator

from pithy.web.response import Response
from pithy.web.sse import SseChannel, SseEvent, SseResponse
from pithy.web.starlette import convert_response
from starlette.types import Message, Scope
from utest import utest_exc, utest_run, utest_val


@utest_run
def test_iterator_response_and_cleanup() -> None:
  for fail in ('', 'head', 'body', 'iterator'):
    closed:list[bool] = []

    def chunks() -> Generator[bytes,None,None]:
      try:
        yield b'first'
        if fail == 'iterator': raise RuntimeError('iterator failed')
        yield b'second'
      finally: closed.append(True)

    source = chunks()
    # A generator closed before it starts does not enter its finally block; use a channel for that case below.
    response = convert_response(Response(body=source))
    utest_val(False, any(key == b'content-length' for key, _ in response.raw_headers))
    messages:list[Message] = []

    async def receive() -> Message: raise AssertionError('receive should not be called')
    async def send(message:Message) -> None:
      if fail == 'head' or (fail == 'body' and message['type'] == 'http.response.body'):
        raise RuntimeError('send failed')
      messages.append(message)

    scope:Scope = {'type': 'http', 'asgi': {'spec_version': '2.4'}}
    if fail: utest_exc(RuntimeError, asyncio.run, response(scope, receive, send))
    else:
      asyncio.run(response(scope, receive, send))
      utest_val(b'firstsecond', b''.join(message.get('body', b'') for message in messages))
    utest_val([] if fail == 'head' else [True], closed)
    utest_exc(StopIteration, next, source)


@utest_run
def test_sse_conversion_and_unstarted_cleanup() -> None:
  for method, fail in (('GET', False), ('HEAD', False), ('GET', True)):
    channel = SseChannel()
    channel.send(SseEvent(data='hello', id='7'))
    channel.finish()
    response = convert_response(SseResponse(channel), method=method)
    headers = dict(response.raw_headers)
    utest_val(b'text/event-stream;charset=utf-8', headers[b'content-type'])
    utest_val(False, b'content-length' in headers)
    messages:list[Message] = []

    async def receive() -> Message: raise AssertionError('receive should not be called')
    async def send(message:Message) -> None:
      if fail: raise RuntimeError('send failed')
      messages.append(message)

    scope:Scope = {'type': 'http', 'asgi': {'spec_version': '2.4'}}
    if fail: utest_exc(RuntimeError, asyncio.run, response(scope, receive, send))
    else:
      asyncio.run(response(scope, receive, send))
      utest_val(b'' if method == 'HEAD' else b'id: 7\ndata: hello\n\n',
        b''.join(message.get('body', b'') for message in messages))
    utest_val(True, channel.closed.is_set())
