# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from sys import stderr
from time import monotonic
from types import TracebackType

from b2sdk.v3 import AbstractProgressListener
from pithy.strings import format_byte_count


class ProgressListener(AbstractProgressListener):
  '''
  A progress listener which prints to TTY stderr.
  '''

  def __init__(self, description:str='Progress') -> None:
    self.description = description
    self.is_tty = stderr.isatty()
    self.total_bytes = 0
    self.completed_bytes = 0
    self.prev_time = monotonic()
    self.total_desc = ''
    super().__init__(description=description)


  def set_total_bytes(self, total_byte_count:int) -> None:
    self.total_bytes = total_byte_count
    self.total_desc = format_byte_count(total_byte_count)


  def bytes_completed(self, byte_count:int) -> None:
      now = monotonic()
      elapsed = now - self.prev_time
      self.completed_bytes = byte_count
      if self.is_tty:
        if elapsed >= 0.1 and self.total_bytes:
          percent = 100.0 * byte_count / self.total_bytes
          print(f'\r{self.description}: {percent:.1f}% of {self.total_desc}…', end='', file=stderr, flush=True)
          self.prev_time = now


  def close(self, exception:BaseException|None=None) -> None:
    try:
      if self.is_tty and self.total_bytes:
        if exception:
          print(f'\\n{self.description}: failed.')
        else:
          print(f'\r{self.description}: 100.0% of {self.total_desc}.', file=stderr)
    finally:
      super().close()



  def __exit__(self, exc_type:type[BaseException], exc_value:BaseException, traceback:TracebackType) -> None:
    'Override AbstractProgressListener.__exit__ to pass is_exception to close().'
    self.close(exception=exc_value)
