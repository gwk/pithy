# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import signal
from typing import Callable, ContextManager

from .typing import OptBaseExc, OptTraceback, OptTypeBaseExc


class Timeout(Exception):
  'Exception indicating that an Alarm timed out.'


class Alarm(ContextManager):

  def __init__(self, timeout:int, msg:str='alarm timed out after {timeout} seconds', on_signal:Callable[[],None]|None=None):
    if not isinstance(timeout, int): raise TypeError(f'timeout must be an int; received: {timeout!r}')
    if timeout < 0: raise TypeError(f'timeout must be nonnegative; received: {timeout!r}')
    self.timeout = timeout
    self.msg = msg
    self.on_signal = on_signal
    self.timed_out = False


  def __enter__(self) -> None:
    if not self.timeout: return
    prev = signal.getsignal(signal.SIGALRM)
    if prev is not signal.SIG_DFL:
      raise Exception(f'task.run encountered previously installed signal handler: {prev}')

    def alarm_handler(signum, current_stack_frame) -> None:
      # since signal handlers carry reentrancy concerns; do not do any IO within the handler.
      self.timed_out = True
      if self.on_signal: self.on_signal() # callback must respect reentrancy limitations.

    signal.signal(signal.SIGALRM, alarm_handler) # set handler.
    signal.alarm(self.timeout) # set alarm.


  def __exit__(self, exc_type:OptTypeBaseExc, exc_value:OptBaseExc, traceback:OptTraceback) -> None:
    if not self.timeout: return
    signal.alarm(0) # disable alarm.
    signal.signal(signal.SIGALRM, signal.SIG_DFL) # uninstall handler.
    if exc_type: return # exception will be reraised.
    if self.timed_out: raise Timeout(self.msg.format(timeout=self.timeout))
