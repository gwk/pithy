# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any, cast

from h11 import Data
from pithy.web.requestconn import BodyAlreadyReadError, BodyTooLargeError
from pithy.web.server import WebServerRequestConn
from utest import utest_exc, utest_run, utest_val


class _FakeConn:
  '''
  Minimal stand-in for the server `_Conn`, for unit-testing WebServerRequestConn without a socket.
  Yields the scripted body as a sequence of h11 Data events, then None to signal the end of the body
  (mirroring how `_Conn.next_data()` returns None once the body is exhausted).
  '''
  def __init__(self, *chunks:bytes) -> None:
    self._events = iter([Data(data=c) for c in chunks])

  def next_data(self) -> Data|None:
    return next(self._events, None)


def _conn(content_length:int|None, *chunks:bytes) -> WebServerRequestConn:
  'A WebServerRequestConn that reads `chunks` from a fake connection.'
  return WebServerRequestConn(content_length=content_length, _conn=cast(Any, _FakeConn(*chunks)))


@utest_run
def _() -> None:
  'read_body: a multi-chunk body with no declared length (content_length None, e.g. chunked) is read fully under the cap.'
  utest_val(b'name=alice', _conn(None, b'na', b'me=', b'alice').read_body(max_bytes=1024))


@utest_run
def _() -> None:
  'read_body: an empty body reads as b"".'
  utest_val(b'', _conn(None).read_body(max_bytes=32))


@utest_run
def _() -> None:
  'read_body: accumulated chunks exceeding the cap raise BodyTooLargeError (the streaming cap, content_length None).'
  # 20 + 20 = 40 bytes streamed past a 32-byte cap; the cap fires on the second chunk, not from a declared length.
  utest_exc(BodyTooLargeError, _conn(None, b'x'*20, b'x'*20).read_body, max_bytes=32)


@utest_run
def _() -> None:
  'read_body: a chunk exactly reaching the cap is allowed; one byte more is rejected.'
  utest_val(b'x'*32, _conn(None, b'x'*32).read_body(max_bytes=32))
  utest_exc(BodyTooLargeError, _conn(None, b'x'*33).read_body, max_bytes=32)


@utest_run
def _() -> None:
  'read_some: a declared Content-Length over the cap is rejected before any body is read.'
  utest_exc(BodyTooLargeError, _conn(100, b'unread').read_body, max_bytes=32)


@utest_run
def _() -> None:
  'read_body: reading again after the body is exhausted raises BodyAlreadyReadError.'
  conn = _conn(None, b'hi')
  utest_val(b'hi', conn.read_body(max_bytes=32))
  utest_exc(BodyAlreadyReadError, conn.read_body, max_bytes=32)
