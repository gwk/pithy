# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from sys import stderr
from time import monotonic
from types import TracebackType
from typing import BinaryIO, Callable, Self, TextIO

from pithy.strings import format_byte_count


class ProgressListener:
  '''
  A progress listener that prints to TTY stderr.
  Satisfies the `tap_backblaze.api.client.Progress` protocol.
  `stream` and `now` are injectable for tests.
  '''

  def __init__(self, description:str='Progress', *, stream:TextIO=stderr, now:Callable[[],float]=monotonic) -> None:
    self.description = description
    self.stream = stream
    self.now = now
    self.is_tty = stream.isatty()
    self.total_bytes = 0
    self.completed_bytes = 0
    self.prev_time = now()
    self.total_desc = ''


  def __enter__(self) -> Self: return self


  def __exit__(self, exc_type:type[BaseException]|None, exc_value:BaseException|None, traceback:TracebackType|None) -> None:
    self.close(exception=exc_value)


  def set_total_bytes(self, total_byte_count:int) -> None:
    self.total_bytes = total_byte_count
    self.total_desc = format_byte_count(total_byte_count)


  def bytes_completed(self, byte_count:int) -> None:
    self.completed_bytes = byte_count
    if self.is_tty and self.total_bytes:
      now = self.now()
      if now - self.prev_time >= 0.1:
        percent = 100.0 * byte_count / self.total_bytes
        print(f'\r{self.description}: {percent:.1f}% of {self.total_desc}…', end='', file=self.stream, flush=True)
        self.prev_time = now


  def close(self, exception:BaseException|None=None) -> None:
    if self.is_tty and self.total_bytes:
      if exception:
        print(f'\n{self.description}: failed.', file=self.stream)
      else:
        print(f'\r{self.description}: 100.0% of {self.total_desc}.', file=self.stream)



class ProgressReader:
  '''
  A binary file wrapper that reads up to `limit` bytes and reports the cumulative count to `on_bytes` as bytes are read.
  `__len__` reports `limit`, so that HTTP libraries size the request body correctly.
  '''

  def __init__(self, f:BinaryIO, *, limit:int, on_bytes:Callable[[int],None]|None=None) -> None:
    self.f = f
    self.limit = limit
    self.on_bytes = on_bytes
    self.count = 0

  def __len__(self) -> int: return self.limit

  def read(self, size:int=-1, /) -> bytes:
    remaining = self.limit - self.count
    if remaining <= 0: return b''
    n = remaining if size < 0 else min(size, remaining)
    data = self.f.read(n)
    self.count += len(data)
    if data and self.on_bytes is not None: self.on_bytes(self.count)
    return data
