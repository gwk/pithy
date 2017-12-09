# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import signal
from types import TracebackType
from typing import Callable, ContextManager, Optional, Type


class Timeout(Exception):
  'Exception indicating that an AlarmManager timed out.'


class AlarmManager(ContextManager):

  def __init__(self, timeout: int, msg:str='alarm timed out after {timeout} seconds', on_signal: Callable[[], None]=None) -> None:
    if not isinstance(timeout, int): raise TypeError(f'timeout must be an int; received: {timeout!r}')
    if timeout < 0: raise TypeError(f'timeout must be nonnegative; received: {timeout!r}')
    self.timeout = timeout
    self.msg = msg
    self.on_signal = on_signal
    self.timed_out = False


  def __enter__(self):
    if not self.timeout: return
    prev = signal.getsignal(signal.SIGALRM)
    if prev is not signal.SIG_DFL:
      raise Exception(f'task.run encountered previously installed signal handler: {prev}')

    def alarm_handler(signum, current_stack_frame):
      # since signal handlers carry reentrancy concerns; do not do any IO within the handler.
      self.timed_out = True
      if self.on_signal: self.on_signal() # callback must respect reentrancy limitations.

    signal.signal(signal.SIGALRM, alarm_handler) # set handler.
    signal.alarm(self.timeout) # set alarm.


  def __exit__(self, exc_type: Optional[Type[BaseException]], exc_value: Optional[BaseException],
   traceback: Optional[TracebackType]) -> None:
    if not self.timeout: return None
    signal.alarm(0) # disable alarm.
    signal.signal(signal.SIGALRM, signal.SIG_DFL) # uninstall handler.
    if exc_type: return None # exception will be reraised.
    if self.timed_out: raise Timeout(self.msg.format(timeout=self.timeout))
    return None
