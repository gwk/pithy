# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from queue import Full
from threading import Event, Thread
from unittest.mock import patch

from pithy.web.response import close_response_body
from pithy.web.sse import SseChannel, SseClosedError, SseEvent, SseResponse
from utest import utest, utest_exc, utest_run, utest_val


@utest_run
def test_event_encoding() -> None:
  event = SseEvent(data='hello\r\nworld\rfin\n', event='update', id='42', retry=1000, comment='a\nb')
  utest(b': a\n: b\nevent: update\nid: 42\nretry: 1000\ndata: hello\ndata: world\ndata: fin\ndata: \n\n', bytes, event)
  utest(b'data: \n\n', bytes, SseEvent(data=''))
  utest(b'data: positional\n\n', bytes, SseEvent('positional'))
  utest(b'event: refresh\ndata: \n\n', bytes, SseEvent(data='', event='refresh'))
  utest(b': heartbeat\n\n', bytes, SseEvent(comment='heartbeat'))
  utest(b'id: \n\n', bytes, SseEvent(id=''))
  utest(b'retry: 0\n\n', bytes, SseEvent(retry=0))
  utest('data: caf\u00e9\n\n'.encode(), bytes, SseEvent(data='caf\u00e9'))
  for text in ('x\ry', 'x\ny'):
    utest_exc(ValueError, SseEvent, data='', event=text)
    utest_exc(ValueError, SseEvent, id=text)
  utest_exc(ValueError, SseEvent, id='x\0y')
  for retry in (-1, 1.5, True): utest_exc(ValueError, lambda: SseEvent(retry=retry)) # type: ignore[arg-type]


@utest_run
def test_event_rejects_useless_and_positional_fields() -> None:
  utest_exc(ValueError, SseEvent)
  utest_exc(ValueError, SseEvent, event='refresh')
  utest_exc(ValueError, SseEvent, event='refresh', comment='never dispatched', id='1')
  utest_exc(TypeError, lambda: SseEvent('x', 'y')) # type: ignore[call-arg]


@utest_run
def test_channel_bounds_and_completion() -> None:
  channel = SseChannel(max_events=1, max_bytes=20)
  channel.send(SseEvent(data='one'))
  utest_exc(Full, channel.send, SseEvent(data='two'))
  utest(SseEvent(data='one'), next, channel)
  utest_exc(Full, channel.send, SseEvent(data='x' * 30))
  channel.send(SseEvent(data='two'))
  channel.finish()
  utest_exc(SseClosedError, channel.send, SseEvent(data=''))
  utest(SseEvent(data='two'), next, channel)
  utest_exc(StopIteration, next, channel)
  utest(False, channel.closed.is_set)
  channel.close()
  channel.close()
  utest(True, channel.closed.is_set)
  utest_exc(StopIteration, next, channel)


@utest_run
def test_close_wakes_waiter_and_discards_events() -> None:
  channel = SseChannel()
  waiting = Event()
  result:list[object] = []

  def consume() -> None:
    waiting.set()
    result.append(next(channel, 'closed'))

  thread = Thread(target=consume)
  thread.start()
  try:
    assert waiting.wait(1)
    channel.close()
    thread.join(1)
    utest(False, thread.is_alive)
    utest_val(['closed'], result)
  finally:
    channel.close()
    thread.join(1)
  buffered = SseChannel()
  buffered.send(SseEvent(data=''))
  buffered.close()
  utest_exc(StopIteration, next, buffered)


@utest_run
def test_headers_heartbeats_and_absolute_lifetime() -> None:
  events = iter([None, SseEvent(data='event'), None, None, SseEvent(data='too late')])
  response = SseResponse(events, heartbeat_interval=10, max_duration=30)
  utest_val('text/event-stream;charset=utf-8', response.headers['content-type'])
  utest_val('no-cache', response.headers['cache-control'])
  utest_val('no', response.headers['x-accel-buffering'])
  utest_val(False, 'content-length' in response.headers)
  with patch('pithy.web.sse.monotonic', return_value=100) as clock:
    body = iter(response.body) # type: ignore[arg-type]
    utest(b'', next, body)
    clock.return_value = 105
    utest(b'data: event\n\n', next, body)
    clock.return_value = 114
    utest(b'', next, body)
    clock.return_value = 115
    utest(b': heartbeat\n\n', next, body)
    clock.return_value = 130
    utest_exc(StopIteration, next, body)
  channel = SseChannel()
  response = SseResponse(channel)
  close_response_body(response.body) # Before the first next(), as for a HEAD response or a rejected stream.
  utest(True, channel.closed.is_set)
  for value in (0, -1, float('inf'), float('nan')):
    utest_exc(ValueError, SseResponse, iter(()), heartbeat_interval=value)
    utest_exc(ValueError, SseResponse, iter(()), max_duration=value)
    utest_exc(ValueError, SseChannel, max_events=0)
    utest_exc(ValueError, SseChannel, max_bytes=0)
