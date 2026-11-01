# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Server-sent events over streaming HTTP responses.

Return `SseResponse(iter(events))` from an endpoint, or create a channel for application callbacks to publish into:
```
channel = SseChannel()
channel.send(SseEvent(data='Ready.', event='status', id='1'))
response = SseResponse(channel)
```
The server owns the response body and closes its source when sending ends, including on disconnect or rejection.
Channels need no producer thread and provide bounded buffering and cooperative waits. A custom iterator must return
periodically, yielding None while idle, so that heartbeats, lifetime limits and shutdown can take effect.
Create subscriptions per request; unsubscribe when the channel's `closed` event is set.

EventSource reconnects automatically after a stream ends. Applications own replay using the request's Last-Event-ID,
authorization, subscription leases and limits per user. A connection lifetime bounds one stream, not an abandoned tab.
Specification: https://html.spec.whatwg.org/multipage/server-sent-events.html
'''

from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass, KW_ONLY
from http import HTTPStatus
from math import inf, isfinite
from queue import Full
from threading import Condition, Event
from time import monotonic

from .headers import ResponseHeadersDict
from .response import Response


_context_keywords_ = ['EventSource', 'Last-Event-ID', 'bounded queue', 'heartbeat', 'server sent events', 'streaming']


@dataclass(frozen=True, slots=True)
class SseEvent:
  '''
  One UTF-8 event or comment. None omits a field.

  Browsers dispatch an event only if it has a data field, which can be an empty string.
  Without data, an event can still carry a comment or update the client's last event ID or retry delay.
  An event name without data would never be dispatched, so it raises ValueError, as does an event with no fields.
  '''

  data:str|None = None
  _:KW_ONLY
  event:str = ''
  id:str|None = None
  retry:int|None = None
  comment:str|None = None

  def __post_init__(self) -> None:
    if '\r' in self.event or '\n' in self.event: raise ValueError('SSE event names must not contain newlines.')
    if self.id is not None and any(c in self.id for c in ('\r', '\n', '\0')):
      raise ValueError('SSE event IDs must not contain newlines or NUL.')
    if self.retry is not None and (type(self.retry) is not int or self.retry < 0):
      raise ValueError('SSE retry must be a nonnegative integer number of milliseconds.')
    if self.data is None:
      if self.event: raise ValueError("SSE event name requires data to be dispatched; use data='' for an empty message.")
      if self.id is None and self.retry is None and self.comment is None: raise ValueError('SSE event has no fields.')


  def __bytes__(self) -> bytes:
    lines:list[str] = []
    if self.comment is not None: lines.extend(f': {line}' for line in _lines(self.comment))
    if self.event: lines.append(f'event: {self.event}')
    if self.id is not None: lines.append(f'id: {self.id}')
    if self.retry is not None: lines.append(f'retry: {self.retry}')
    if self.data is not None: lines.extend(f'data: {line}' for line in _lines(self.data))
    return ('\n'.join(lines) + '\n\n').encode('utf-8')


class SseResponse(Response):
  '''An SSE response with heartbeats and a finite lifetime, independent of activity.

  `events` yields SseEvent, or None to give the sender an opportunity to check its deadlines while idle.
  `max_duration` defaults to five minutes; the native server can impose a shorter `stream_max_duration`.
  Expiration is normal completion. Reconnecting clients authenticate again and may supply Last-Event-ID.
  Heartbeats are comments and do not dispatch browser events. Proxy buffering must also be disabled in deployment.
  '''

  def __init__(self, events:Iterator[SseEvent|None], *, headers:ResponseHeadersDict|None=None,
   heartbeat_interval:float=15.0, max_duration:float=300.0) -> None:
    for name, value in (('heartbeat_interval', heartbeat_interval), ('max_duration', max_duration)):
      if not isfinite(value) or value <= 0: raise ValueError(f'{name} must be finite and positive; received: {value!r}.')
    response_headers:ResponseHeadersDict = {'cache-control': 'no-cache', 'x-accel-buffering': 'no'}
    if headers is not None: response_headers.update(headers)
    super().__init__(HTTPStatus.OK, body=_SseBody(events, heartbeat_interval, max_duration),
      headers=response_headers, media_type='text/event-stream')


class SseClosedError(Exception):
  'An application tried to publish to a finished or closed SSE channel.'


class SseChannel(Iterator[SseEvent|None]):
  '''A bounded channel for one response, with nonblocking publishing and cancellation-aware consumer waits.

  `send` raises queue.Full if either capacity is exceeded; the application chooses whether to drop, retry or end a stream.
  `finish` ends publishing and lets queued events drain. `close` discards pending events and wakes the consumer.
  The response owner calls `close` even when the body was never iterated, such as HEAD or admission rejection.
  `closed` signals that resources and subscriptions can be released; it is set by close, not by finish.
  '''

  def __init__(self, *, max_events:int=128, max_bytes:int=1 << 20) -> None:
    if max_events <= 0 or max_bytes <= 0: raise ValueError('SSE channel capacities must be positive.')
    self.closed = Event()
    self._condition = Condition()
    self._events:deque[tuple[SseEvent,int]] = deque()
    self._bytes = 0
    self._max_events = max_events
    self._max_bytes = max_bytes
    self._finished = False


  def send(self, event:SseEvent) -> None:
    'Publish without blocking. Raise SseClosedError after finish or close, and queue.Full at capacity.'
    size = len(bytes(event))
    with self._condition:
      if self._finished or self.closed.is_set(): raise SseClosedError('SSE channel is closed for publishing.')
      if len(self._events) >= self._max_events or self._bytes + size > self._max_bytes: raise Full
      self._events.append((event, size))
      self._bytes += size
      self._condition.notify()


  def finish(self) -> None:
    'End publishing, allowing already queued events to be sent.'
    with self._condition:
      self._finished = True
      self._condition.notify_all()


  def close(self) -> None:
    with self._condition:
      self.closed.set()
      self._events.clear()
      self._bytes = 0
      self._condition.notify_all()


  def __next__(self) -> SseEvent|None:
    return self.poll(0.25)


  def poll(self, timeout:float) -> SseEvent|None:
    'Wait up to timeout seconds for an event; return None while idle, or raise StopIteration when finished.'
    with self._condition:
      self._condition.wait_for(lambda: bool(self._events) or self._finished or self.closed.is_set(), timeout=timeout)
      if self._events:
        event, size = self._events.popleft()
        self._bytes -= size
        return event
      if self._finished or self.closed.is_set(): raise StopIteration
      return None


class _SseBody(Iterator[bytes]):

  def __init__(self, events:Iterator[SseEvent|None], heartbeat_interval:float, max_duration:float) -> None:
    self.events = events
    self.heartbeat_interval = heartbeat_interval
    self.max_duration = max_duration
    self.started:float|None = None
    self.last_send = 0.0
    self.deadline = inf


  def __next__(self) -> bytes:
    now = monotonic()
    if self.started is None:
      self.started = self.last_send = now
      self.deadline = min(self.deadline, now + self.max_duration)
    if now >= self.deadline: raise StopIteration
    if isinstance(self.events, SseChannel):
      timeout = min(0.25, self.deadline - now, max(0, self.heartbeat_interval - (now - self.last_send)))
      event = self.events.poll(timeout)
    else: event = next(self.events)
    now = monotonic()
    if now >= self.deadline: raise StopIteration
    if event is not None:
      self.last_send = now
      return bytes(event)
    if now - self.last_send >= self.heartbeat_interval:
      self.last_send = now
      return b': heartbeat\n\n'
    return b''


  def close(self) -> None:
    if (close := getattr(self.events, 'close', None)) is not None: close()


def _lines(text:str) -> list[str]:
  return text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
